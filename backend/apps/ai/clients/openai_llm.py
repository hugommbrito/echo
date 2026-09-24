"""OpenAI Responses API with structured outputs.

Same `parse()` contract as `AnthropicClient`, used for learners who only bring an OpenAI key
(and for everyone when no Anthropic key is configured at all). Differences that matter:

- the system prompt goes in `instructions`; OpenAI caches prompts automatically, so there is no
  `cache_control` — we pass a stable `prompt_cache_key` per system prompt to help the router;
- `effort` maps to `reasoning.effort` (low | medium | high);
- `usage.input_tokens` includes cached tokens on OpenAI; we split them out so the pricing table
  charges cached input at the cached rate, like the Anthropic client does.
"""

from __future__ import annotations

import hashlib
import time
from typing import TypeVar

import openai
from django.conf import settings
from pydantic import BaseModel

from apps.ai.clients.base import LLMResult
from apps.ai.exceptions import AIAuthError, AIError, AIRefusal

T = TypeVar("T", bound=BaseModel)


def _find_refusal(response) -> str | None:
    for item in getattr(response, "output", None) or []:
        if getattr(item, "type", None) != "message":
            continue
        for part in getattr(item, "content", None) or []:
            if getattr(part, "type", None) == "refusal":
                return getattr(part, "refusal", "") or "refused"
    return None


class OpenAILLMClient:
    provider = "openai"

    def __init__(self, api_key: str | None = None, timeout: float = 120.0, max_retries: int = 3):
        # The SDK retries 408/409/429/5xx and connection errors with backoff; 4xx are not retried.
        self._client = openai.OpenAI(
            api_key=api_key or settings.OPENAI_API_KEY, timeout=timeout, max_retries=max_retries
        )

    def parse(
        self,
        *,
        model: str,
        system: str,
        user: str,
        output_format: type[T],
        effort: str = "medium",
        max_tokens: int = 8000,
        timeout: float | None = None,
    ) -> LLMResult[T]:
        started = time.monotonic()
        client = self._client.with_options(timeout=timeout) if timeout else self._client
        cache_key = "echo-" + hashlib.sha1(system.encode("utf-8")).hexdigest()[:16]
        try:
            response = client.responses.parse(
                model=model,
                instructions=system,
                input=[{"role": "user", "content": user}],
                text_format=output_format,
                reasoning={"effort": effort},
                max_output_tokens=max_tokens,
                prompt_cache_key=cache_key,
            )
        except openai.AuthenticationError as exc:
            raise AIAuthError(f"OpenAI rejected the API key: {exc.message}") from exc
        except openai.PermissionDeniedError as exc:
            raise AIAuthError(f"OpenAI denied access with this API key: {exc.message}") from exc
        except openai.RateLimitError as exc:
            raise AIError(f"OpenAI rate limit: {exc.message}") from exc
        except openai.APIStatusError as exc:
            raise AIError(f"OpenAI API error {exc.status_code}: {exc.message}") from exc
        except openai.APIConnectionError as exc:
            raise AIError(f"OpenAI connection error: {exc}") from exc

        latency_ms = int((time.monotonic() - started) * 1000)
        refusal = _find_refusal(response)
        if refusal:
            raise AIRefusal(f"Model refused: {refusal}")
        status = getattr(response, "status", None) or "completed"
        if status != "completed":
            details = getattr(response, "incomplete_details", None)
            reason = getattr(details, "reason", None) or getattr(response, "error", None)
            raise AIError(
                f"OpenAI response {status} ({reason}); increase max_tokens or check the schema."
            )
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise AIError("No structured output from OpenAI; check the schema.")
        usage = getattr(response, "usage", None)
        input_tokens = (getattr(usage, "input_tokens", 0) or 0) if usage else 0
        output_tokens = (getattr(usage, "output_tokens", 0) or 0) if usage else 0
        details = getattr(usage, "input_tokens_details", None) if usage else None
        cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0
        try:
            raw = response.model_dump(mode="json")
        except Exception:  # pragma: no cover - defensive, raw is telemetry only
            raw = {"id": getattr(response, "id", None)}
        return LLMResult(
            parsed=parsed,
            model=model,  # the requested id, not the dated snapshot: it must match pricing
            input_tokens=max(0, input_tokens - cached),
            output_tokens=output_tokens,
            cache_read_input_tokens=cached,
            cache_creation_input_tokens=0,
            latency_ms=latency_ms,
            stop_reason=status,
            raw=raw,
        )
