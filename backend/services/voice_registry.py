"""Loads the voice library from voices/voices.json."""
from __future__ import annotations

import json
from dataclasses import dataclass

from backend.config.settings import VOICES_FILE


@dataclass(frozen=True)
class Voice:
    id: str
    name: str
    gender: str
    style: str
    language: str
    description: str = ""


def load_voices() -> list[Voice]:
    with open(VOICES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Voice(**v) for v in data["voices"]]


def voices_by_id() -> dict[str, Voice]:
    return {v.id: v for v in load_voices()}
