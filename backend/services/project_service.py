"""Filesystem-backed project storage.

projects/
    <slug>/
        project.json   (id, name, voice_id, speed, created_at, updated_at)
        script.txt
        voice.wav
        voice.mp3
        metadata.json
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from backend.config.settings import PROJECTS_DIR

_lock = Lock()


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _unique_slug(base_slug: str) -> str:
    slug = base_slug
    n = 2
    while (PROJECTS_DIR / slug).exists():
        slug = f"{base_slug}-{n}"
        n += 1
    return slug


def create_project(name: str, script: str = "", voice_id: str | None = None, speed: float = 1.0) -> dict:
    with _lock:
        slug = _unique_slug(_slugify(name))
        project_dir = PROJECTS_DIR / slug
        project_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "id": slug,
            "name": name,
            "voice_id": voice_id,
            "speed": speed,
            "created_at": _now(),
            "updated_at": _now(),
        }
        (project_dir / "project.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
        (project_dir / "script.txt").write_text(script, encoding="utf-8")
        return record


def list_projects() -> list[dict]:
    if not PROJECTS_DIR.exists():
        return []
    projects = []
    for project_dir in sorted(PROJECTS_DIR.iterdir()):
        record_path = project_dir / "project.json"
        if not record_path.exists():
            continue
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        record["has_audio"] = (project_dir / "voice.wav").exists()
        record["has_mp3"] = (project_dir / "voice.mp3").exists()
        projects.append(record)
    projects.sort(key=lambda p: p.get("updated_at", ""), reverse=True)
    return projects


def get_project(project_id: str) -> dict | None:
    project_dir = PROJECTS_DIR / project_id
    record_path = project_dir / "project.json"
    if not record_path.exists():
        return None
    record = json.loads(record_path.read_text(encoding="utf-8"))
    script_path = project_dir / "script.txt"
    record["script"] = script_path.read_text(encoding="utf-8") if script_path.exists() else ""
    record["has_audio"] = (project_dir / "voice.wav").exists()
    record["has_mp3"] = (project_dir / "voice.mp3").exists()
    meta_path = project_dir / "metadata.json"
    record["metadata"] = (
        json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else None
    )
    return record


def delete_project(project_id: str) -> bool:
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.exists():
        return False
    shutil.rmtree(project_dir)
    return True


def save_generation_into_project(
    project_id: str,
    script: str,
    voice_id: str,
    speed: float,
    wav_path: Path | None,
    mp3_path: Path | None,
    metadata: dict,
) -> None:
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.exists():
        raise FileNotFoundError(f"Project not found: {project_id}")
    (project_dir / "script.txt").write_text(script, encoding="utf-8")
    if wav_path and wav_path.exists():
        shutil.copyfile(wav_path, project_dir / "voice.wav")
    if mp3_path and mp3_path.exists():
        shutil.copyfile(mp3_path, project_dir / "voice.mp3")
    (project_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    record_path = project_dir / "project.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record.update({"voice_id": voice_id, "speed": speed, "updated_at": _now()})
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
