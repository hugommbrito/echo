import pytest

from apps.accounts.models import LanguageProfile

pytestmark = pytest.mark.django_db


def test_csrf_endpoint_sets_cookie_and_returns_token(api_client):
    response = api_client.get("/api/v1/auth/csrf/")
    assert response.status_code == 200
    assert response.json()["csrfToken"]
    assert "csrftoken" in response.cookies


def test_login_logout_flow(api_client, user_a):
    bad = api_client.post(
        "/api/v1/auth/login/", {"email": "ana@example.com", "password": "wrong"}, format="json"
    )
    assert bad.status_code == 401
    assert bad.json()["code"] == "invalid_credentials"

    ok = api_client.post(
        "/api/v1/auth/login/", {"email": "Ana@Example.com", "password": "pass12345"}, format="json"
    )
    assert ok.status_code == 200, ok.content
    body = ok.json()
    assert body["email"] == "ana@example.com"
    assert "level" not in body and "default_new_cards_per_day" not in body
    assert len(body["languages"]) == 1
    profile = body["languages"][0]
    assert profile["code"] == "en" and profile["name"] == "Inglês" and profile["is_active"] is True
    assert profile["default_new_cards_per_day"] == 3 and profile["activated_at"]
    assert profile["level"] == {
        "rating": 1150,
        "band": "A2",
        "provisional": True,
        "counted_attempts": 0,
        "initial_rating": 1150,
    }

    assert api_client.get("/api/v1/me/").status_code == 200
    assert api_client.post("/api/v1/auth/logout/").status_code == 204
    assert api_client.get("/api/v1/me/").status_code == 403


def test_patch_me_preferences(client_a):
    response = client_a.patch(
        "/api/v1/me/",
        {"timezone": "America/Toronto", "feedback_language": "en", "default_new_cards_per_day": 5},
        format="json",
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["timezone"] == "America/Toronto"
    assert body["feedback_language"] == "en"
    # the daily target now lives on the language profile; the legacy key is ignored
    assert body["languages"][0]["default_new_cards_per_day"] == 3


def test_patch_me_rejects_invalid_values_and_readonly_fields(client_a, user_a):
    bad_tz = client_a.patch("/api/v1/me/", {"timezone": "Mars/Olympus"}, format="json")
    assert bad_tz.status_code == 400
    assert bad_tz.json()["errors"]["timezone"]

    ignored = client_a.patch(
        "/api/v1/me/",
        {
            "email": "new@example.com",
            "is_staff": True,
            "languages": [{"code": "en", "level": {"rating": 2000}}],
        },
        format="json",
    )
    assert ignored.status_code == 200
    user_a.refresh_from_db()
    assert user_a.email == "ana@example.com" and user_a.is_staff is False
    assert LanguageProfile.all_users.get(user=user_a, language="en").level_rating == 1150


def test_healthcheck(api_client):
    assert api_client.get("/healthz/").json() == {"status": "ok"}


def test_me_exposes_preferences_thinking_time_and_ai_status(client_a):
    body = client_a.get("/api/v1/me/").json()
    assert body["question_mode"] == "read" and body["show_thinking_timer"] is True
    assert body["languages"][0]["thinking_time"] == {
        "baseline_seconds": 6.0,
        "samples": 0,
        "is_default": True,
    }
    assert body["ai"] == {
        "llm_provider": "anthropic",
        "speech_available": True,
        "anthropic": {"configured": False, "hint": None, "source": "global"},
        "openai": {"configured": False, "hint": None, "source": "global"},
    }
    updated = client_a.patch(
        "/api/v1/me/", {"question_mode": "listen", "show_thinking_timer": False}, format="json"
    )
    assert updated.status_code == 200, updated.content
    assert updated.json()["question_mode"] == "listen"
    assert updated.json()["show_thinking_timer"] is False
    assert (
        client_a.patch("/api/v1/me/", {"question_mode": "loud"}, format="json").status_code == 400
    )


def test_login_response_includes_thinking_time_and_ai_status(api_client, user_a):
    """`/me/` is serialised at login, before any owner context exists."""
    body = api_client.post(
        "/api/v1/auth/login/", {"email": "ana@example.com", "password": "pass12345"}, format="json"
    ).json()
    assert body["languages"][0]["thinking_time"]["is_default"] is True
    assert body["ai"]["llm_provider"] == "anthropic"


def test_me_never_leaks_api_keys(client_a, user_a):
    user_a.anthropic_api_key = "sk-ant-api03-secretsecret1234"
    user_a.openai_api_key = "sk-proj-othersecret5678"
    user_a.save()
    response = client_a.get("/api/v1/me/")
    assert b"secret" not in response.content
    ai = response.json()["ai"]
    assert ai["anthropic"] == {"configured": True, "hint": "…1234", "source": "user"}
    assert ai["openai"] == {"configured": True, "hint": "…5678", "source": "user"}
    assert ai["llm_provider"] == "anthropic" and ai["speech_available"] is True

    ignored = client_a.patch("/api/v1/me/", {"anthropic_api_key": "sk-ant-evil"}, format="json")
    assert ignored.status_code == 200
    user_a.refresh_from_db()
    assert user_a.anthropic_api_key == "sk-ant-api03-secretsecret1234"


def test_only_openai_key_routes_everything_to_openai(client_a, user_a):
    user_a.openai_api_key = "sk-proj-onlyopenai0001"
    user_a.save()
    ai = client_a.get("/api/v1/me/").json()["ai"]
    assert ai["llm_provider"] == "openai"
    assert ai["anthropic"] == {"configured": False, "hint": None, "source": "none"}
    assert ai["openai"] == {"configured": True, "hint": "…0001", "source": "user"}


def test_only_anthropic_key_without_global_openai_has_no_speech(client_a, user_a, settings):
    settings.OPENAI_API_KEY = None
    user_a.anthropic_api_key = "sk-ant-api03-onlyanthropic0002"
    user_a.save()
    ai = client_a.get("/api/v1/me/").json()["ai"]
    assert ai["llm_provider"] == "anthropic" and ai["speech_available"] is False
    assert ai["openai"] == {"configured": False, "hint": None, "source": "none"}
