"""Object-storage paths: every user's files live under their own prefix."""

from __future__ import annotations

import pathlib

MIME_TO_EXT = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
}


def extension_for(mime_type: str | None, filename: str | None = None) -> str:
    base = (mime_type or "").split(";")[0].strip().lower()
    if base in MIME_TO_EXT:
        return MIME_TO_EXT[base]
    if filename:
        suffix = pathlib.PurePosixPath(filename).suffix.lstrip(".").lower()
        if suffix:
            return suffix
    return "bin"


def attempt_audio_path(instance, filename: str) -> str:
    ext = extension_for(getattr(instance, "audio_mime", None), filename)
    return f"users/{instance.user_id}/attempts/{instance.id}.{ext}"


def card_audio_path(instance, filename: str) -> str:
    """Spoken question (TTS) of a card, next to the user's attempt recordings."""
    ext = pathlib.PurePosixPath(filename).suffix.lstrip(".").lower() or "mp3"
    return f"users/{instance.user_id}/cards/{instance.id}.{ext}"
