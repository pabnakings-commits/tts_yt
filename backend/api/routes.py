from __future__ import annotations

import platform
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.config.settings import ffmpeg_status, gpu_status, settings
from backend.logging_setup import logger
from backend.models.schemas import (
    GenerateRequest,
    JobProgress,
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
    SettingsModel,
    SettingsUpdate,
    SystemStatus,
    Voice as VoiceSchema,
    VoiceList,
)
from backend.services import project_service
from backend.services.job_manager import job_manager
from backend.services.tts_service import get_engine
from backend.services.voice_registry import load_voices

router = APIRouter(prefix="/api")


@router.get("/voices", response_model=VoiceList)
def get_voices():
    try:
        voices = load_voices()
    except Exception:
        logger.exception("Failed to load voices.json")
        raise HTTPException(status_code=500, detail="Could not load the voice library.")
    return VoiceList(
        engine="kokoro",
        model="kokoro-v1.0",
        voices=[VoiceSchema(**v.__dict__) for v in voices],
    )


@router.get("/system", response_model=SystemStatus)
def system_status():
    gpu = gpu_status()
    ffmpeg = ffmpeg_status()
    engine = get_engine(settings.as_dict()["engine"])
    return SystemStatus(
        python_version=platform.python_version(),
        device="cpu",
        gpu_detected=gpu["gpu_detected"],
        gpu_name=gpu["name"],
        ffmpeg_installed=ffmpeg["installed"],
        ffmpeg_version=ffmpeg["version"],
        model_ready=engine.model_ready(),
        engine=engine.name,
    )


@router.get("/settings", response_model=SettingsModel)
def get_settings():
    return SettingsModel(**settings.as_dict())


@router.post("/settings", response_model=SettingsModel)
def update_settings(body: SettingsUpdate):
    if body.output_dir:
        path = Path(body.output_dir).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise HTTPException(
                status_code=400, detail=f"Could not use that output folder: {exc}"
            )
    updated = settings.update(
        output_format=body.output_format, output_dir=body.output_dir
    )
    return SettingsModel(**updated)


@router.post("/generate", status_code=202)
def generate(body: GenerateRequest):
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Script text cannot be empty.")
    if len(text) > 200_000:
        raise HTTPException(
            status_code=400,
            detail="Script is too long (max 200,000 characters). Please split it up.",
        )
    valid_ids = {v.id for v in load_voices()}
    if body.voice_id not in valid_ids:
        raise HTTPException(status_code=400, detail=f"Unknown voice id: {body.voice_id}")

    job = job_manager.submit(body)
    return {"job_id": job.id}


@router.get("/jobs/{job_id}", response_model=JobProgress)
def get_job(job_id: str):
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobProgress(
        job_id=job.id,
        state=job.state,
        progress=round(job.progress, 1),
        message=job.message,
        error=job.error,
        project_id=job.project_id,
        audio_id=job.audio_id,
        result=job.result,
    )


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects():
    return project_service.list_projects()


@router.post("/projects", response_model=ProjectDetail, status_code=201)
def create_project(body: ProjectCreate):
    record = project_service.create_project(
        body.name, body.script, body.voice_id, body.speed
    )
    record["has_audio"] = False
    return record


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str):
    record = project_service.get_project(project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return record


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str):
    ok = project_service.delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found.")
    return None


def _resolve_audio_dir(audio_id: str) -> Path:
    candidate = settings.output_dir / audio_id
    if candidate.exists():
        return candidate
    from backend.config.settings import PROJECTS_DIR

    candidate = PROJECTS_DIR / audio_id
    if candidate.exists():
        return candidate
    raise HTTPException(status_code=404, detail="Audio not found.")


@router.get("/audio/{audio_id}")
def get_audio(audio_id: str):
    return get_audio_wav(audio_id)


@router.get("/audio/{audio_id}/wav")
def get_audio_wav(audio_id: str):
    audio_dir = _resolve_audio_dir(audio_id)
    wav_path = audio_dir / "voice.wav"
    if not wav_path.exists():
        raise HTTPException(status_code=404, detail="WAV file not found for this audio id.")
    return FileResponse(
        wav_path, media_type="audio/wav", filename=f"{audio_id}.wav"
    )


@router.get("/audio/{audio_id}/mp3")
def get_audio_mp3(audio_id: str):
    audio_dir = _resolve_audio_dir(audio_id)
    mp3_path = audio_dir / "voice.mp3"
    if not mp3_path.exists():
        raise HTTPException(
            status_code=404,
            detail="MP3 file not found for this audio id. It may not have been generated.",
        )
    return FileResponse(
        mp3_path, media_type="audio/mpeg", filename=f"{audio_id}.mp3"
    )


@router.get("/audio/{audio_id}/metadata")
def get_audio_metadata(audio_id: str):
    audio_dir = _resolve_audio_dir(audio_id)
    meta_path = audio_dir / "metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Metadata not found for this audio id.")
    import json

    return json.loads(meta_path.read_text(encoding="utf-8"))
