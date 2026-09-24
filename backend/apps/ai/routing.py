"""Which provider and which API key serve a given user (bring your own key).

Rules agreed with the product owner:

- no own key            -> everything on the global keys (Anthropic for text if present,
                           else OpenAI);
- only an OpenAI key    -> everything (text, transcription, TTS) on the user's OpenAI key;
- only an Anthropic key -> text on the user's Anthropic key; speech (Whisper/TTS) on the user's
                           OpenAI key if any, else on the global OpenAI key;
- both keys             -> both are the user's.

`ECHO_AI_PROVIDER=fake` bypasses routing entirely (see `apps.ai.clients`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from django.conf import settings

Provider = Literal["anthropic", "openai"]

KEY_SOURCE_USER = "user"
KEY_SOURCE_GLOBAL = "global"


@dataclass(frozen=True)
class ResolvedKey:
    api_key: str
    source: str  # KEY_SOURCE_USER | KEY_SOURCE_GLOBAL

    def __repr__(self) -> str:  # never leak the key in logs or tracebacks
        return f"ResolvedKey(source={self.source!r}, hint={key_hint(self.api_key)!r})"


@dataclass(frozen=True)
class AIRouting:
    llm_provider: Provider | None  # None = no text-capable key anywhere
    llm_key: ResolvedKey | None
    openai_key: ResolvedKey | None  # speech: transcription and text-to-speech

    @property
    def speech_available(self) -> bool:
        return self.openai_key is not None


def key_hint(value: str | None) -> str | None:
    """Last four characters of a secret, for display (`…a1b2`); None when unset."""
    if not value:
        return None
    return "…" + value[-4:]


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def own_keys(user) -> tuple[str | None, str | None]:
    return _clean(getattr(user, "anthropic_api_key", None)), _clean(
        getattr(user, "openai_api_key", None)
    )


def resolve_routing(user) -> AIRouting:
    own_anthropic, own_openai = own_keys(user)
    global_anthropic = _clean(settings.ANTHROPIC_API_KEY)
    global_openai = _clean(settings.OPENAI_API_KEY)

    if own_openai and not own_anthropic:
        key = ResolvedKey(own_openai, KEY_SOURCE_USER)
        return AIRouting("openai", key, key)
    if own_anthropic:
        if own_openai:
            speech = ResolvedKey(own_openai, KEY_SOURCE_USER)
        elif global_openai:
            speech = ResolvedKey(global_openai, KEY_SOURCE_GLOBAL)
        else:
            speech = None
        return AIRouting("anthropic", ResolvedKey(own_anthropic, KEY_SOURCE_USER), speech)
    speech = ResolvedKey(global_openai, KEY_SOURCE_GLOBAL) if global_openai else None
    if global_anthropic:
        return AIRouting("anthropic", ResolvedKey(global_anthropic, KEY_SOURCE_GLOBAL), speech)
    if speech is not None:
        return AIRouting("openai", speech, speech)
    return AIRouting(None, None, None)


def public_status(user) -> dict:
    """What `/me/` exposes: whether a key of the user's own exists and where calls will go.

    Never includes the key itself, only a four-character hint.
    """
    routing = resolve_routing(user)
    own_anthropic, own_openai = own_keys(user)
    if own_anthropic:
        anthropic_source = KEY_SOURCE_USER
    elif routing.llm_provider == "anthropic" and routing.llm_key is not None:
        anthropic_source = routing.llm_key.source
    else:
        anthropic_source = "none"
    openai_source = routing.openai_key.source if routing.openai_key is not None else "none"
    return {
        "llm_provider": routing.llm_provider,
        "speech_available": routing.speech_available,
        "anthropic": {
            "configured": bool(own_anthropic),
            "hint": key_hint(own_anthropic),
            "source": anthropic_source,
        },
        "openai": {
            "configured": bool(own_openai),
            "hint": key_hint(own_openai),
            "source": openai_source,
        },
    }
