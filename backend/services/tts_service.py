"""TTS engine abstraction.

`TTSEngine` is the interface every engine must implement. `KokoroEngine` is
the primary (and currently only) implementation, running Kokoro-82M via
onnxruntime on CPU. The model is loaded exactly once per process and reused
for every generation (see `get_engine()`).

To add another engine later (e.g. Piper as a fallback):
    1. Create a class implementing `TTSEngine` (see the interface below).
    2. Register it in `_ENGINES` at the bottom of this file.
    3. Point `Settings.engine` at its registry key.
No other part of the app needs to change - the API, job manager and audio
pipeline all talk to the `TTSEngine` interface only.
"""
from __future__ import annotations

import abc
import threading
from typing import Optional

import numpy as np

from backend.config.settings import MODELS_DIR, VOICES_FILE
from backend.logging_setup import logger
from backend.services import model_downloader
from backend.services.voice_registry import Voice, load_voices

# Kokoro's native output sample rate.
KOKORO_SAMPLE_RATE = 24000

# Kokoro's create() takes phoneme-length-bounded chunks internally, but we
# still cap how much raw text we hand it per call so job progress can be
# reported per paragraph/section for long scripts.
MAX_CHARS_PER_CALL = 900


class TTSEngine(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def load(self) -> None:
        """Load the model into memory. Must be idempotent and thread-safe."""

    @property
    @abc.abstractmethod
    def is_loaded(self) -> bool:
        ...

    @abc.abstractmethod
    def list_voices(self) -> list[Voice]:
        ...

    @abc.abstractmethod
    def synthesize(
        self, text: str, voice_id: str, speed: float = 1.0
    ) -> tuple[np.ndarray, int]:
        """Return (float32 mono samples, sample_rate) for one chunk of text."""

    @abc.abstractmethod
    def model_ready(self) -> bool:
        """Whether the model files required by this engine are already cached."""

    def ensure_model_files(self, on_progress=None) -> None:
        """Download model files if this engine needs them and they're missing."""
        return None


class KokoroEngine(TTSEngine):
    name = "kokoro"

    def __init__(self) -> None:
        self._kokoro = None
        self._lock = threading.Lock()
        self._voices = load_voices()
        self._valid_voice_ids = {v.id for v in self._voices}

    def model_ready(self) -> bool:
        return model_downloader.is_ready()

    def ensure_model_files(self, on_progress=None) -> None:
        model_downloader.ensure_models(on_progress=on_progress)

    def load(self) -> None:
        if self._kokoro is not None:
            return
        with self._lock:
            if self._kokoro is not None:
                return
            self.ensure_model_files()
            logger.info("Loading Kokoro model into memory (CPU)...")
            # Imported lazily so the rest of the app can start even if the
            # kokoro_onnx package / onnxruntime isn't installed yet.
            from kokoro_onnx import Kokoro

            self._kokoro = Kokoro(
                str(model_downloader.MODEL_FILE.path),
                str(model_downloader.VOICES_BIN_FILE.path),
            )
            logger.info("Kokoro model loaded and ready for reuse.")

    @property
    def is_loaded(self) -> bool:
        return self._kokoro is not None

    def list_voices(self) -> list[Voice]:
        return self._voices

    def synthesize(
        self, text: str, voice_id: str, speed: float = 1.0
    ) -> tuple[np.ndarray, int]:
        if voice_id not in self._valid_voice_ids:
            raise ValueError(f"Unknown voice id: {voice_id!r}")
        self.load()
        assert self._kokoro is not None
        samples, sample_rate = self._kokoro.create(
            text,
            voice=voice_id,
            speed=float(speed),
            lang="en-us",
            trim=True,
        )
        return np.asarray(samples, dtype=np.float32), int(sample_rate)


class PiperEngine(TTSEngine):
    """Placeholder for a future CPU-friendly fallback engine (Piper TTS).

    Not wired up by default because Kokoro runs fine on CPU-only machines.
    Implement this if you need an alternative engine - see the module
    docstring above for the steps to register it.
    """

    name = "piper"

    def load(self) -> None:
        raise NotImplementedError(
            "Piper engine is not implemented yet. Kokoro is the active engine."
        )

    @property
    def is_loaded(self) -> bool:
        return False

    def list_voices(self) -> list[Voice]:
        return []

    def synthesize(self, text: str, voice_id: str, speed: float = 1.0):
        raise NotImplementedError

    def model_ready(self) -> bool:
        return False


_ENGINES: dict[str, type[TTSEngine]] = {
    "kokoro": KokoroEngine,
    "piper": PiperEngine,
}

_engine_instances: dict[str, TTSEngine] = {}
_registry_lock = threading.Lock()


def get_engine(name: str = "kokoro") -> TTSEngine:
    with _registry_lock:
        if name not in _engine_instances:
            if name not in _ENGINES:
                raise ValueError(f"Unknown TTS engine: {name!r}")
            _engine_instances[name] = _ENGINES[name]()
        return _engine_instances[name]
