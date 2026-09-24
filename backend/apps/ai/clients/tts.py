"""Text-to-speech via OpenAI (`gpt-4o-mini-tts` by default) for the spoken question."""

from __future__ import annotations

import time

import openai
from django.conf import settings

from apps.ai.clients.base import SpeechResult
from apps.ai.exceptions import AIAuthError, SpeechSynthesisError

MODELS_WITH_INSTRUCTIONS = ("gpt-4o-mini-tts",)
MAX_INPUT_CHARS = 4096


class OpenAISpeechClient:
    provider = "openai"

    def __init__(self, api_key: str | None = None, timeout: float | None = None):
        self._client = openai.OpenAI(
            api_key=api_key or settings.OPENAI_API_KEY,
            timeout=timeout or settings.ECHO_TTS_TIMEOUT_SECONDS,
            max_retries=2,
        )

    def synthesize(
        self,
        text: str,
        *,
        model: str,
        voice: str,
        instructions: str | None = None,
        response_format: str = "mp3",
        timeout: float | None = None,
    ) -> SpeechResult:
        text = (text or "").strip()[:MAX_INPUT_CHARS]
        if not text:
            raise SpeechSynthesisError("Nothing to synthesise.")
        kwargs = {"model": model, "voice": voice, "input": text, "response_format": response_format}
        if instructions and model in MODELS_WITH_INSTRUCTIONS:
            kwargs["instructions"] = instructions
        client = self._client.with_options(timeout=timeout) if timeout else self._client
        started = time.monotonic()
        try:
            response = client.audio.speech.create(**kwargs)
            audio = response.content
        except openai.AuthenticationError as exc:
            raise AIAuthError(f"OpenAI rejected the API key: {exc.message}") from exc
        except openai.PermissionDeniedError as exc:
            raise AIAuthError(f"OpenAI denied access with this API key: {exc.message}") from exc
        except openai.APIStatusError as exc:
            raise SpeechSynthesisError(
                f"OpenAI API error {exc.status_code}: {exc.message}"
            ) from exc
        except openai.APIConnectionError as exc:
            raise SpeechSynthesisError(f"OpenAI connection error: {exc}") from exc
        if not audio:
            raise SpeechSynthesisError("OpenAI returned empty audio.")
        return SpeechResult(
            audio=audio,
            model=model,
            voice=voice,
            response_format=response_format,
            characters=len(text),
            latency_ms=int((time.monotonic() - started) * 1000),
        )
