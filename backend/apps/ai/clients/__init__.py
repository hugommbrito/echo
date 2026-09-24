"""Provider selection and per-user key routing.

`ECHO_AI_PROVIDER=fake` swaps every external call for a deterministic fake. Otherwise each
factory resolves the user's routing (own keys first, global keys as fallback — see
`apps.ai.routing`) and returns `(client, resolved_key)`, so callers can log which key paid.
Live clients are cached per (kind, provider, key) to reuse HTTP connection pools.
"""

from __future__ import annotations

from functools import lru_cache

from django.conf import settings

from apps.ai.exceptions import AIConfigurationError
from apps.ai.routing import KEY_SOURCE_GLOBAL, ResolvedKey, resolve_routing


def _fake() -> bool:
    return settings.ECHO_AI_PROVIDER == "fake"


def _fake_key(user, kind: str) -> ResolvedKey:
    """Fakes never call a provider, but the key *source* still follows the routing rules so the
    logs (and tests) show who would have paid."""
    routing = resolve_routing(user)
    key = routing.llm_key if kind == "llm" else routing.openai_key
    return ResolvedKey(api_key="fake", source=key.source if key else KEY_SOURCE_GLOBAL)


@lru_cache(maxsize=32)
def _client(kind: str, provider: str, api_key: str):
    if kind == "llm":
        if provider == "openai":
            from apps.ai.clients.openai_llm import OpenAILLMClient

            return OpenAILLMClient(api_key=api_key)
        from apps.ai.clients.anthropic_client import AnthropicClient

        return AnthropicClient(api_key=api_key)
    if kind == "transcriber":
        from apps.ai.clients.transcription import OpenAITranscriptionClient

        return OpenAITranscriptionClient(api_key=api_key)
    if kind == "tts":
        from apps.ai.clients.tts import OpenAISpeechClient

        return OpenAISpeechClient(api_key=api_key)
    raise ValueError(kind)  # pragma: no cover


def get_llm(user):
    """Structured-output LLM client for text tasks (generation, evaluation, improved answer)."""
    if _fake():
        from apps.ai.clients.fake import FakeLLM

        return FakeLLM(), _fake_key(user, "llm")
    routing = resolve_routing(user)
    if routing.llm_provider is None or routing.llm_key is None:
        raise AIConfigurationError(
            "No API key available for text generation: add an Anthropic or OpenAI key for this "
            "user, or configure a global one."
        )
    return _client("llm", routing.llm_provider, routing.llm_key.api_key), routing.llm_key


def get_transcriber(user):
    if _fake():
        from apps.ai.clients.fake import FakeTranscriber

        return FakeTranscriber(), _fake_key(user, "speech")
    routing = resolve_routing(user)
    if routing.openai_key is None:
        raise AIConfigurationError(
            "No OpenAI API key available for transcription: add one for this user or a global one."
        )
    return _client("transcriber", "openai", routing.openai_key.api_key), routing.openai_key


def get_tts(user):
    if _fake():
        from apps.ai.clients.fake import FakeTTS

        return FakeTTS(), _fake_key(user, "speech")
    routing = resolve_routing(user)
    if routing.openai_key is None:
        raise AIConfigurationError(
            "No OpenAI API key available for text-to-speech: add one for this user or a global one."
        )
    return _client("tts", "openai", routing.openai_key.api_key), routing.openai_key


def get_prober():
    if _fake():
        from apps.ai.clients.fake import FakeProbe

        return FakeProbe()
    from apps.ai.clients.ffprobe import FFProbe

    return FFProbe()
