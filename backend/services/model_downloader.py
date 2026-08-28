"""Downloads and caches the Kokoro ONNX model files.

Files are stored in `models/` and reused on every subsequent run - they are
only fetched once. Downloads are streamed to a `.part` file and only moved
into place once complete, so an interrupted download never leaves a
corrupt file that looks valid.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import requests

from backend.config.settings import MODELS_DIR
from backend.logging_setup import logger

KOKORO_RELEASE_BASE = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1"
)

# Minimum acceptable sizes (bytes) - a much smaller file means a failed /
# truncated download or an HTML error page instead of the real asset.
_MIN_SIZES = {
    "kokoro-v1.0.onnx": 150_000_000,
    "voices-v1.0.bin": 10_000_000,
}


@dataclass
class ModelFile:
    filename: str
    url: str

    @property
    def path(self) -> Path:
        return MODELS_DIR / self.filename


MODEL_FILE = ModelFile("kokoro-v1.0.onnx", f"{KOKORO_RELEASE_BASE}/kokoro-v1.0.onnx")
VOICES_BIN_FILE = ModelFile(
    "voices-v1.0.bin", f"{KOKORO_RELEASE_BASE}/voices-v1.0.bin"
)

REQUIRED_FILES = [MODEL_FILE, VOICES_BIN_FILE]

ProgressCallback = Callable[[str, float], None]


def is_ready() -> bool:
    return all(
        f.path.exists() and f.path.stat().st_size >= _MIN_SIZES[f.filename]
        for f in REQUIRED_FILES
    )


def missing_files() -> list[ModelFile]:
    return [
        f
        for f in REQUIRED_FILES
        if not (f.path.exists() and f.path.stat().st_size >= _MIN_SIZES[f.filename])
    ]


def _download_one(model_file: ModelFile, on_progress: Optional[ProgressCallback]) -> None:
    tmp_path = model_file.path.with_suffix(model_file.path.suffix + ".part")
    logger.info("Downloading %s -> %s", model_file.url, model_file.path)

    with requests.get(model_file.url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0)) or _MIN_SIZES.get(
            model_file.filename, 0
        )
        downloaded = 0
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if on_progress and total:
                    on_progress(model_file.filename, min(downloaded / total, 1.0))

    size = tmp_path.stat().st_size
    if size < _MIN_SIZES.get(model_file.filename, 1):
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Download of {model_file.filename} looked incomplete "
            f"({size} bytes) - please check your internet connection and retry."
        )
    tmp_path.replace(model_file.path)
    logger.info("Saved %s (%d bytes)", model_file.path, size)


def ensure_models(on_progress: Optional[ProgressCallback] = None) -> None:
    """Download any missing model files. No-op if everything is already cached."""
    to_fetch = missing_files()
    if not to_fetch:
        logger.info("Kokoro model files already present, skipping download.")
        return

    for model_file in to_fetch:
        try:
            _download_one(model_file, on_progress)
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Failed to download {model_file.filename} from "
                f"{model_file.url}: {exc}"
            ) from exc
