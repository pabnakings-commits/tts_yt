"""Application configuration and persistent settings.

All paths are resolved relative to the project root (the parent of the
`backend/` directory) so the app works the same whether it's launched via
start.bat, uvicorn, or run() directly.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from threading import Lock
from typing import Literal

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
MODELS_DIR = ROOT_DIR / "models"
VOICES_DIR = ROOT_DIR / "voices"
PROJECTS_DIR = ROOT_DIR / "projects"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "output"
LOGS_DIR = ROOT_DIR / "logs"
FRONTEND_DIST_DIR = ROOT_DIR / "frontend" / "dist"
SETTINGS_FILE = ROOT_DIR / "backend" / "config" / "user_settings.json"
VOICES_FILE = VOICES_DIR / "voices.json"

for d in (MODELS_DIR, VOICES_DIR, PROJECTS_DIR, DEFAULT_OUTPUT_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)

OutputFormat = Literal["wav", "mp3", "wav+mp3"]

_DEFAULTS = {
    "engine": "kokoro",
    "device": "cpu",
    "output_format": "wav+mp3",
    "output_dir": str(DEFAULT_OUTPUT_DIR),
    "max_concurrent_generations": 1,
}

_lock = Lock()


class Settings:
    """Small JSON-file-backed settings store (thread-safe, single process)."""

    def __init__(self) -> None:
        self._data = dict(_DEFAULTS)
        self._load()

    def _load(self) -> None:
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data.update({k: v for k, v in saved.items() if k in _DEFAULTS})
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self) -> None:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def as_dict(self) -> dict:
        with _lock:
            return dict(self._data)

    def update(self, **kwargs) -> dict:
        with _lock:
            for key, value in kwargs.items():
                if value is None:
                    continue
                if key not in _DEFAULTS:
                    continue
                self._data[key] = value
            self._save()
            return dict(self._data)

    @property
    def output_dir(self) -> Path:
        p = Path(self._data["output_dir"])
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def output_format(self) -> str:
        return self._data["output_format"]


settings = Settings()


def ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def ffmpeg_status() -> dict:
    path = ffmpeg_path()
    if not path:
        return {"installed": False, "path": None, "version": None}
    try:
        out = subprocess.run(
            [path, "-version"], capture_output=True, text=True, timeout=5
        )
        version_line = out.stdout.splitlines()[0] if out.stdout else "unknown"
    except Exception:
        version_line = "unknown"
    return {"installed": True, "path": path, "version": version_line}


def gpu_status() -> dict:
    """Detect an NVIDIA GPU purely for informational purposes.

    The app always runs TTS inference on CPU (no CUDA build of
    onnxruntime is installed), so this never changes inference behavior -
    it only lets the Settings page tell the user what was detected.
    """
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return {"gpu_detected": False, "name": None}
    try:
        out = subprocess.run(
            [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        name = out.stdout.strip().splitlines()[0] if out.stdout.strip() else None
        return {"gpu_detected": bool(name), "name": name}
    except Exception:
        return {"gpu_detected": False, "name": None}
