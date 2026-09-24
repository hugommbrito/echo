"""Thin wrapper over the Anthropic SDK: structured outputs, caching, refusal handling."""

from __future__ import annotations

import time
from typing import TypeVar

import anthropic
from django.conf import settings
from pydantic import BaseModel

from apps.ai.clients.base import LLMResult
from apps.ai.exceptions import AIAuthError, AIError, AIRefusal

T = TypeVar("T", bound=BaseModel)


class AnthropicClient:
    provider = "anthropic"

    def __init__(self, api_key: str | None = None, timeout: float = 120.0, max_retries: int = 3):
        # The SDK retries 408/409/429/5xx and connection errors with backoff; 4xx are not retried.
        self._client = anthropic.Anthropic(
            api_key=api_key or settings.ANTHROPIC_API_KEY, timeout=timeout, max_retries=max_retries
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
        try:
            response = client.messages.parse(
                model=model,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
                output_format=output_format,
                output_config={"effort": effort},
                thinking={"type": "adaptive"},
            )
        except anthropic.RateLimitError as exc:
            raise AIError(f"Anthropic rate limit: {exc.message}") from exc
        except anthropic.AuthenticationError as exc:
            raise AIAuthError(f"Anthropic rejected the API key: {exc.message}") from exc
        except anthropic.PermissionDeniedError as exc:
            raise AIAuthError(f"Anthropic denied access with this API key: {exc.message}") from exc
        except anthropic.APIStatusError as exc:
            raise AIError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise AIError(f"Anthropic connection error: {exc}") from exc

        latency_ms = int((time.monotonic() - started) * 1000)
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise AIRefusal(
                f"Model refused ({getattr(details, 'category', None)}): "
                f"{getattr(details, 'explanation', '')}"
            )
        parsed = response.parsed_output
        if parsed is None:
            raise AIError(
                f"No structured output (stop_reason={response.stop_reason}); "
                "increase max_tokens or check the schema."
            )
        usage = response.usage
        return LLMResult(
            parsed=parsed,
            model=response.model,
            input_tokens=usage.input_tokens or 0,
            output_tokens=usage.output_tokens or 0,
            cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            latency_ms=latency_ms,
            stop_reason=response.stop_reason or "",
            raw=response.to_dict(),
        )
