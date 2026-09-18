"""Speech-to-text via OpenAI (`whisper-1` by default; `gpt-*-transcribe` for A/B tests)."""

from __future__ import annotations

import time
from pathlib import Path

import openai
from django.conf import settings

from apps.ai.clients.base import TranscriptionResult
from apps.ai.exceptions import TranscriptionError
from apps.ai.prompts import whisper_prompt


class OpenAITranscriptionClient:
    provider = "openai"

    def __init__(self, api_key: str | None = None, timeout: float = 120.0):
        self._client = openai.OpenAI(
            api_key=api_key or settings.OPENAI_API_KEY, timeout=timeout, max_retries=2
        )

    def transcribe(self, path: str | Path, *, model: str | None = None) -> TranscriptionResult:
        model = model or settings.ECHO_TRANSCRIPTION_MODEL
        verbose = model == "whisper-1"  # only whisper-1 returns verbose_json (segments + duration)
        started = time.monotonic()
        try:
            with open(path, "rb") as audio:
                kwargs = {
                    "model": model,
                    "file": audio,
                    "language": "en",
                    "prompt": whisper_prompt(),
                    "response_format": "verbose_json" if verbose else "json",
                }
                if verbose:
                    kwargs["temperature"] = 0
                response = self._client.audio.transcriptions.create(**kwargs)
        except openai.APIStatusError as exc:
            raise TranscriptionError(f"OpenAI API error {exc.status_code}: {exc.message}") from exc
        except openai.APIConnectionError as exc:
            raise TranscriptionError(f"OpenAI connection error: {exc}") from exc

        latency_ms = int((time.monotonic() - started) * 1000)
        text = (getattr(response, "text", "") or "").strip()
        segments = [
            {"start": s.start, "end": s.end, "text": s.text}
            for s in (getattr(response, "segments", None) or [])
        ]
        duration = getattr(response, "duration", None)
        raw = response.model_dump() if hasattr(response, "model_dump") else {"text": text}
        return TranscriptionResult(
            text=text,
            model=model,
            segments=segments,
            duration_seconds=float(duration) if duration is not None else None,
            latency_ms=latency_ms,
            raw=raw,
        )
