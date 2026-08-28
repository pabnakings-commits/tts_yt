"""Background job queue for TTS generation.

Generation runs one job at a time (a single worker) so a CPU-only machine
never gets multiple heavy synthesis jobs competing for the same cores.
Additional requests simply wait in the queue - the UI stays responsive
because jobs run in a worker thread while FastAPI keeps serving status
polls and other requests from the event loop.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.config.settings import settings
from backend.logging_setup import logger
from backend.models.schemas import GenerateRequest, JobState
from backend.services import audio_service, project_service
from backend.services.tts_service import get_engine
from backend.services.text_utils import chunk_script
from backend.services.voice_registry import voices_by_id


@dataclass
class Job:
    id: str
    request: GenerateRequest
    state: JobState = "queued"
    progress: float = 0.0
    message: str = "Queued"
    error: Optional[str] = None
    audio_id: Optional[str] = None
    project_id: Optional[str] = None
    result: Optional[dict] = None
    created_at: float = field(default_factory=time.time)


def _next_output_id(base_dir: Path) -> str:
    base_dir.mkdir(parents=True, exist_ok=True)
    existing = [
        p.name for p in base_dir.iterdir() if p.is_dir() and re.match(r"^project_\d+$", p.name)
    ]
    max_n = 0
    for name in existing:
        n = int(name.split("_")[1])
        max_n = max(max_n, n)
    return f"project_{max_n + 1:03d}"


class JobManager:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self._queue: "asyncio.Queue[str]" = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.get_event_loop().create_task(self._worker())

    def submit(self, request: GenerateRequest) -> Job:
        job_id = uuid.uuid4().hex[:12]
        job = Job(id=job_id, request=request)
        self.jobs[job_id] = job
        self._queue.put_nowait(job_id)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)

    async def _worker(self) -> None:
        while True:
            job_id = await self._queue.get()
            job = self.jobs.get(job_id)
            if job is None:
                continue
            try:
                await self._run_job(job)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Job %s failed", job_id)
                job.state = "error"
                job.error = _friendly_error(exc)
                job.message = "Generation failed"
            finally:
                self._queue.task_done()

    async def _run_job(self, job: Job) -> None:
        req = job.request
        voice = voices_by_id().get(req.voice_id)
        if voice is None:
            raise ValueError(f"Unknown voice: {req.voice_id}")

        job.state = "preparing_model"
        job.message = "Preparing model..."
        job.progress = 2

        engine = get_engine(settings.as_dict()["engine"])

        def _on_download_progress(filename: str, pct: float) -> None:
            job.message = f"Downloading {filename}... {pct * 100:.0f}%"
            job.progress = 2 + pct * 8

        if not engine.model_ready():
            await asyncio.to_thread(engine.ensure_model_files, _on_download_progress)

        await asyncio.to_thread(engine.load)
        job.progress = 10

        chunks = chunk_script(req.text)
        if not chunks:
            raise ValueError("The script is empty after cleanup - nothing to generate.")

        job.state = "generating"
        segments = []
        sample_rate = 24000
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            job.message = f"Generating voice... segment {i + 1}/{total}"
            job.progress = 10 + 60 * (i / total)
            samples, sample_rate = await asyncio.to_thread(
                engine.synthesize, chunk, req.voice_id, req.speed
            )
            segments.append(samples)

        job.state = "combining_segments"
        job.message = "Combining segments..."
        job.progress = 74
        joined = audio_service.join_segments(segments, sample_rate)

        job.state = "processing_audio"
        job.message = "Processing audio..."
        job.progress = 85
        processed = await asyncio.to_thread(
            audio_service.process_audio, joined, sample_rate
        )

        job.state = "finalizing"
        job.message = "Finalizing..."
        job.progress = 92

        output_format = req.output_format or settings.output_format
        output_root = settings.output_dir
        output_id = _next_output_id(output_root)
        output_dir = output_root / output_id
        output_dir.mkdir(parents=True, exist_ok=True)

        wav_path = output_dir / "voice.wav"
        mp3_path = output_dir / "voice.mp3"
        await asyncio.to_thread(
            audio_service.write_wav, processed, sample_rate, wav_path
        )

        generated_mp3 = False
        if output_format in ("mp3", "wav+mp3"):
            await asyncio.to_thread(audio_service.write_mp3, wav_path, mp3_path)
            generated_mp3 = True

        if output_format == "mp3" and wav_path.exists():
            # Keep the WAV too (internal high-quality master) but the user
            # only asked for MP3 as the deliverable format; both stay on
            # disk since WAV is our source of truth for re-export.
            pass

        duration = audio_service.duration_seconds(processed, sample_rate)
        metadata = {
            "voice": voice.name,
            "voice_id": voice.id,
            "text": req.text,
            "char_count": len(req.text),
            "speed": req.speed,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generation_seconds": round(time.time() - job.created_at, 2),
            "duration_seconds": duration,
            "engine": engine.name,
            "model": "kokoro-v1.0",
            "sample_rate": sample_rate,
            "segments": total,
        }
        (output_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )

        project_id = None
        if req.project_name:
            existing = {p["name"]: p["id"] for p in project_service.list_projects()}
            project_id = existing.get(req.project_name)
            if project_id is None:
                created = project_service.create_project(
                    req.project_name, req.text, req.voice_id, req.speed
                )
                project_id = created["id"]
            project_service.save_generation_into_project(
                project_id,
                req.text,
                req.voice_id,
                req.speed,
                wav_path,
                mp3_path if generated_mp3 else None,
                metadata,
            )

        job.audio_id = output_id
        job.project_id = project_id
        job.result = {
            "audio_id": output_id,
            "project_id": project_id,
            "duration_seconds": duration,
            "has_mp3": generated_mp3,
            "metadata": metadata,
        }
        job.state = "done"
        job.message = "Done"
        job.progress = 100


def _friendly_error(exc: Exception) -> str:
    message = str(exc)
    if isinstance(exc, ValueError):
        return message
    if isinstance(exc, RuntimeError):
        return message
    if isinstance(exc, FileNotFoundError):
        return "A required file was not found."
    if isinstance(exc, MemoryError):
        return "Ran out of memory while generating audio. Try a shorter script."
    return "An unexpected error occurred while generating audio. Check logs/app.log for details."


job_manager = JobManager()
