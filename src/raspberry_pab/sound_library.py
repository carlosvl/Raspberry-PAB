"""Helpers for uploaded alert sound files."""

from __future__ import annotations

from pathlib import Path

MAX_SOUND_BYTES = 8 * 1024 * 1024

ALLOWED_SOUND_EXTENSIONS: dict[str, str] = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
}

_CONTENT_TYPE_TO_EXTENSION: dict[str, str] = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/ogg": ".ogg",
    "application/ogg": ".ogg",
}

ALLOWED_SOUND_CONTENT_TYPES = set(_CONTENT_TYPE_TO_EXTENSION) | {
    "application/octet-stream",
}


def extension_for_upload(filename: str | None, content_type: str | None) -> str | None:
    if filename:
        suffix = Path(filename).suffix.lower()
        if suffix in ALLOWED_SOUND_EXTENSIONS:
            return suffix
    if content_type:
        normalized = content_type.split(";")[0].strip().lower()
        return _CONTENT_TYPE_TO_EXTENSION.get(normalized)
    return None


def stored_name_for(sound_id: int, extension: str) -> str:
    return f"{sound_id}{extension}"
