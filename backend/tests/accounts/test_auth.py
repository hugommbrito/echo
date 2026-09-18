import pytest

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
    assert body["level"] == {
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
    assert body["default_new_cards_per_day"] == 5


def test_patch_me_rejects_invalid_values_and_readonly_fields(client_a, user_a):
    bad_tz = client_a.patch("/api/v1/me/", {"timezone": "Mars/Olympus"}, format="json")
    assert bad_tz.status_code == 400
    assert bad_tz.json()["errors"]["timezone"]

    too_many = client_a.patch("/api/v1/me/", {"default_new_cards_per_day": 999}, format="json")
    assert too_many.status_code == 400

    ignored = client_a.patch(
        "/api/v1/me/",
        {"email": "new@example.com", "is_staff": True, "level": {"rating": 2000}},
        format="json",
    )
    assert ignored.status_code == 200
    user_a.refresh_from_db()
    assert (
        user_a.email == "ana@example.com"
        and user_a.is_staff is False
        and user_a.level_rating == 1150
    )


def test_healthcheck(api_client):
    assert api_client.get("/healthz/").json() == {"status": "ok"}
