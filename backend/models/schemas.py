"""Pydantic models shared across the API."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

JobState = Literal[
    "queued",
    "preparing_model",
    "generating",
    "processing_audio",
    "combining_segments",
    "finalizing",
    "done",
    "error",
]


class Voice(BaseModel):
    id: str
    name: str
    gender: Literal["male", "female"]
    style: str
    language: str
    description: str = ""


class VoiceList(BaseModel):
    engine: str
    model: str
    voices: list[Voice]


class GenerateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=200_000)
    voice_id: str
    speed: float = Field(1.0, ge=0.75, le=1.25)
    output_format: Optional[Literal["wav", "mp3", "wav+mp3"]] = None
    project_name: Optional[str] = Field(
        None, description="If provided, save the result into this project."
    )


class JobProgress(BaseModel):
    job_id: str
    state: JobState
    progress: float = Field(0, ge=0, le=100)
    message: str = ""
    error: Optional[str] = None
    project_id: Optional[str] = None
    audio_id: Optional[str] = None
    result: Optional[dict] = None


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    script: str = ""
    voice_id: Optional[str] = None
    speed: float = 1.0


class ProjectSummary(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    has_audio: bool
    has_mp3: bool = False
    voice_id: Optional[str] = None


class ProjectDetail(ProjectSummary):
    script: str
    speed: float
    metadata: Optional[dict] = None


class AudioMetadata(BaseModel):
    voice_id: str
    voice_name: str
    text_preview: str
    char_count: int
    speed: float
    generated_at: str
    generation_seconds: float
    duration_seconds: float
    engine: str
    model: str
    sample_rate: int


class SettingsModel(BaseModel):
    engine: str
    device: str
    output_format: Literal["wav", "mp3", "wav+mp3"]
    output_dir: str
    max_concurrent_generations: int


class SettingsUpdate(BaseModel):
    output_format: Optional[Literal["wav", "mp3", "wav+mp3"]] = None
    output_dir: Optional[str] = None


class SystemStatus(BaseModel):
    python_version: str
    device: str
    gpu_detected: bool
    gpu_name: Optional[str] = None
    ffmpeg_installed: bool
    ffmpeg_version: Optional[str] = None
    model_ready: bool
    engine: str
