"""Lightweight, non-destructive audio post-processing and file export.

Philosophy per spec: keep the voice natural. We only do the minimum needed
for consistent, clip-free, professional-sounding output:
  - peak-safe loudness normalization to a consistent target level
  - trimming leading/trailing silence
  - capping unnaturally long internal silences
  - joining multi-chunk generations with a clean, consistent pause
No pitch shifting, no heavy EQ, no aggressive compression.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from backend.config.settings import ffmpeg_path
from backend.logging_setup import logger

TARGET_RMS_DBFS = -20.0
PEAK_CEILING_DBFS = -1.0
SILENCE_THRESHOLD_DB = -45.0
CHUNK_JOIN_PAUSE_MS = 260
MAX_INTERNAL_SILENCE_MS = 900


def _db_to_amp(db: float) -> float:
    return float(10 ** (db / 20))


def normalize_audio(samples: np.ndarray) -> np.ndarray:
    if samples.size == 0:
        return samples
    rms = float(np.sqrt(np.mean(np.square(samples))))
    if rms > 1e-6:
        gain = _db_to_amp(TARGET_RMS_DBFS) / rms
        samples = samples * gain
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    ceiling = _db_to_amp(PEAK_CEILING_DBFS)
    if peak > ceiling:
        samples = samples * (ceiling / peak)
    return np.clip(samples, -1.0, 1.0).astype(np.float32)


def trim_edges(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    if samples.size == 0:
        return samples
    threshold = _db_to_amp(SILENCE_THRESHOLD_DB)
    above = np.where(np.abs(samples) > threshold)[0]
    if above.size == 0:
        return samples
    pad = int(0.03 * sample_rate)
    start = max(0, int(above[0]) - pad)
    end = min(samples.size, int(above[-1]) + pad)
    return samples[start:end]


def cap_internal_silence(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    """Shorten any internal silent gap longer than MAX_INTERNAL_SILENCE_MS."""
    if samples.size == 0:
        return samples
    threshold = _db_to_amp(SILENCE_THRESHOLD_DB)
    window = max(1, int(0.02 * sample_rate))  # 20ms windows
    is_silent = np.array(
        [
            np.max(np.abs(samples[i : i + window])) < threshold
            for i in range(0, samples.size, window)
        ]
    )
    max_windows = max(1, int((MAX_INTERNAL_SILENCE_MS / 1000) / 0.02))

    out_chunks = []
    i = 0
    n = len(is_silent)
    while i < n:
        if is_silent[i]:
            j = i
            while j < n and is_silent[j]:
                j += 1
            run_len = j - i
            keep = min(run_len, max_windows)
            start_sample = i * window
            end_sample = start_sample + keep * window
            out_chunks.append(samples[start_sample:end_sample])
            i = j
        else:
            j = i
            while j < n and not is_silent[j]:
                j += 1
            start_sample = i * window
            end_sample = min(samples.size, j * window)
            out_chunks.append(samples[start_sample:end_sample])
            i = j
    return np.concatenate(out_chunks) if out_chunks else samples


def join_segments(segments: list[np.ndarray], sample_rate: int) -> np.ndarray:
    if not segments:
        return np.array([], dtype=np.float32)
    if len(segments) == 1:
        return segments[0]
    pause_samples = int(sample_rate * CHUNK_JOIN_PAUSE_MS / 1000)
    pause = np.zeros(pause_samples, dtype=np.float32)
    parts: list[np.ndarray] = []
    for idx, seg in enumerate(segments):
        parts.append(seg)
        if idx != len(segments) - 1:
            parts.append(pause)
    return np.concatenate(parts)


def process_audio(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    samples = trim_edges(samples, sample_rate)
    samples = cap_internal_silence(samples, sample_rate)
    samples = normalize_audio(samples)
    return samples


def write_wav(samples: np.ndarray, sample_rate: int, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), samples, sample_rate, subtype="PCM_16")


def write_mp3(wav_path: Path, mp3_path: Path, bitrate: str = "192k") -> None:
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg was not found on this system. MP3 export requires FFmpeg. "
            "Install it and make sure it's on your PATH, then try again."
        )
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(wav_path),
        "-codec:a",
        "libmp3lame",
        "-b:a",
        bitrate,
        str(mp3_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("ffmpeg failed: %s", result.stderr)
        raise RuntimeError("FFmpeg failed to convert audio to MP3.")


def duration_seconds(samples: np.ndarray, sample_rate: int) -> float:
    if sample_rate <= 0:
        return 0.0
    return round(len(samples) / sample_rate, 3)
