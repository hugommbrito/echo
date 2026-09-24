"""Which provider and key serve a user (bring your own key) — see `apps.ai.routing`."""

import pytest

from apps.ai import clients
from apps.ai.clients.anthropic_client import AnthropicClient
from apps.ai.clients.fake import FakeLLM
from apps.ai.clients.openai_llm import OpenAILLMClient
from apps.ai.exceptions import AIConfigurationError
from apps.ai.routing import public_status, resolve_routing

pytestmark = pytest.mark.django_db

G_ANTHROPIC, G_OPENAI = "sk-ant-api03-global-aaaa", "sk-proj-global-bbbb"
U_ANTHROPIC, U_OPENAI = "sk-ant-api03-user-cccc", "sk-proj-user-dddd"


def _configure(settings, user, own_anthropic, own_openai, global_anthropic, global_openai):
    settings.ANTHROPIC_API_KEY = global_anthropic
    settings.OPENAI_API_KEY = global_openai
    user.anthropic_api_key = own_anthropic
    user.openai_api_key = own_openai
    user.save()
    return user


@pytest.mark.parametrize(
    "own_a, own_o, glob_a, glob_o, llm, llm_key, llm_src, speech_key, speech_src",
    [
        ("", "", G_ANTHROPIC, G_OPENAI, "anthropic", G_ANTHROPIC, "global", G_OPENAI, "global"),
        ("", U_OPENAI, G_ANTHROPIC, G_OPENAI, "openai", U_OPENAI, "user", U_OPENAI, "user"),
        (
            U_ANTHROPIC,
            "",
            G_ANTHROPIC,
            G_OPENAI,
            "anthropic",
            U_ANTHROPIC,
            "user",
            G_OPENAI,
            "global",
        ),
        (
            U_ANTHROPIC,
            U_OPENAI,
            G_ANTHROPIC,
            G_OPENAI,
            "anthropic",
            U_ANTHROPIC,
            "user",
            U_OPENAI,
            "user",
        ),
        ("", "", None, G_OPENAI, "openai", G_OPENAI, "global", G_OPENAI, "global"),
        ("", "", G_ANTHROPIC, None, "anthropic", G_ANTHROPIC, "global", None, None),
        (U_ANTHROPIC, "", None, None, "anthropic", U_ANTHROPIC, "user", None, None),
        ("", "", None, None, None, None, None, None, None),
    ],
)
def test_routing_matrix(
    settings, user_a, own_a, own_o, glob_a, glob_o, llm, llm_key, llm_src, speech_key, speech_src
):
    user = _configure(settings, user_a, own_a, own_o, glob_a, glob_o)
    routing = resolve_routing(user)
    assert routing.llm_provider == llm
    assert (routing.llm_key.api_key if routing.llm_key else None) == llm_key
    assert (routing.llm_key.source if routing.llm_key else None) == llm_src
    assert (routing.openai_key.api_key if routing.openai_key else None) == speech_key
    assert (routing.openai_key.source if routing.openai_key else None) == speech_src
    assert routing.speech_available is (speech_key is not None)


def test_public_status_never_contains_a_key(settings, user_a):
    user = _configure(settings, user_a, U_ANTHROPIC, "", G_ANTHROPIC, G_OPENAI)
    status = public_status(user)
    assert status == {
        "llm_provider": "anthropic",
        "speech_available": True,
        "anthropic": {"configured": True, "hint": "…cccc", "source": "user"},
        "openai": {"configured": False, "hint": None, "source": "global"},
    }
    assert "sk-" not in str(status)
    assert "sk-" not in repr(resolve_routing(user))


def test_public_status_only_openai_marks_anthropic_unused(settings, user_a):
    user = _configure(settings, user_a, "", U_OPENAI, G_ANTHROPIC, G_OPENAI)
    status = public_status(user)
    assert status["llm_provider"] == "openai"
    assert status["anthropic"]["source"] == "none" and status["openai"]["source"] == "user"


def test_live_factories_pick_the_client_and_cache_per_key(settings, user_a, user_b):
    settings.ECHO_AI_PROVIDER = "live"
    clients._client.cache_clear()
    only_openai = _configure(settings, user_a, "", U_OPENAI, G_ANTHROPIC, G_OPENAI)
    client, key = clients.get_llm(only_openai)
    assert isinstance(client, OpenAILLMClient) and key.source == "user"
    transcriber, t_key = clients.get_transcriber(only_openai)
    assert transcriber.provider == "openai" and t_key.api_key == U_OPENAI
    tts, s_key = clients.get_tts(only_openai)
    assert tts.provider == "openai" and s_key.source == "user"

    user_b.save()
    client_b, key_b = clients.get_llm(user_b)  # no own keys -> global Anthropic
    assert isinstance(client_b, AnthropicClient) and key_b.source == "global"
    assert clients.get_llm(user_b)[0] is client_b  # cached per (kind, provider, key)
    assert clients.get_llm(only_openai)[0] is client

    settings.ANTHROPIC_API_KEY = None
    settings.OPENAI_API_KEY = None
    with pytest.raises(AIConfigurationError):
        clients.get_llm(user_b)
    with pytest.raises(AIConfigurationError):
        clients.get_transcriber(user_b)
    with pytest.raises(AIConfigurationError):
        clients.get_tts(user_b)
    clients._client.cache_clear()


def test_fake_provider_ignores_keys_but_reports_the_source(settings, user_a):
    user = _configure(settings, user_a, "", U_OPENAI, G_ANTHROPIC, G_OPENAI)
    client, key = clients.get_llm(user)
    assert isinstance(client, FakeLLM) and key.source == "user" and key.api_key == "fake"
    user = _configure(settings, user_a, "", "", G_ANTHROPIC, G_OPENAI)
    assert clients.get_llm(user)[1].source == "global"
