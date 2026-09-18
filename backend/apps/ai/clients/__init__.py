"""Provider selection.

`ECHO_AI_PROVIDER=fake` swaps every external call for a deterministic fake.
"""

from __future__ import annotations

from functools import lru_cache

from django.conf import settings


def _fake() -> bool:
    return settings.ECHO_AI_PROVIDER == "fake"


@lru_cache(maxsize=1)
def _live_llm():
    from apps.ai.clients.anthropic_client import AnthropicClient

    return AnthropicClient()


@lru_cache(maxsize=1)
def _live_transcriber():
    from apps.ai.clients.transcription import OpenAITranscriptionClient

    return OpenAITranscriptionClient()


def get_llm():
    if _fake():
        from apps.ai.clients.fake import FakeLLM

        return FakeLLM()
    return _live_llm()


def get_transcriber():
    if _fake():
        from apps.ai.clients.fake import FakeTranscriber

        return FakeTranscriber()
    return _live_transcriber()


def get_prober():
    if _fake():
        from apps.ai.clients.fake import FakeProbe

        return FakeProbe()
    from apps.ai.clients.ffprobe import FFProbe

    return FFProbe()
