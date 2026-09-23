"""Self-serve language activation, pause/resume and per-language daily target."""

import pytest

from apps.accounts.models import LanguageProfile

pytestmark = pytest.mark.django_db


def test_catalog_lists_supported_languages(client_a):
    body = client_a.get("/api/v1/languages/").json()
    assert body == [
        {
            "code": "en",
            "name": "Inglês",
            "name_en": "English",
            "starting_levels": ["A1", "A2", "B1"],
        },
        {
            "code": "fr",
            "name": "Francês (Canadá/Québec)",
            "name_en": "French (Canada/Québec)",
            "starting_levels": ["A1", "A2", "B1"],
        },
    ]


def test_activate_language_with_self_placement(client_a, user_a):
    default = client_a.post("/api/v1/me/languages/", {"language": "fr"}, format="json")
    assert default.status_code == 201, default.content
    body = default.json()
    assert body["code"] == "fr" and body["name"] == "Francês (Canadá/Québec)"
    assert body["is_active"] is True and body["default_new_cards_per_day"] == 3
    assert body["level"] == {
        "rating": 900,
        "band": "A1",
        "provisional": True,
        "counted_attempts": 0,
        "initial_rating": 900,
    }
    profile = LanguageProfile.all_users.get(user=user_a, language="fr")
    assert profile.level_rating == profile.level_rating_initial == 900

    me = client_a.get("/api/v1/me/").json()
    assert [lang["code"] for lang in me["languages"]] == ["en", "fr"]

    duplicate = client_a.post("/api/v1/me/languages/", {"language": "fr"}, format="json")
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "language_exists"


@pytest.mark.parametrize(("level", "rating"), [("A1", 900), ("A2", 1100), ("B1", 1300)])
def test_starting_level_sets_the_band_centre(client_b, level, rating):
    LanguageProfile.all_users.filter(language="fr").delete()
    body = client_b.post(
        "/api/v1/me/languages/", {"language": "fr", "starting_level": level}, format="json"
    ).json()
    assert body["level"]["rating"] == rating and body["level"]["band"] == level


def test_activation_validation(client_a):
    unknown = client_a.post("/api/v1/me/languages/", {"language": "xx"}, format="json")
    assert unknown.status_code == 400
    too_high = client_a.post(
        "/api/v1/me/languages/", {"language": "fr", "starting_level": "C1"}, format="json"
    )
    assert too_high.status_code == 400 and "starting_level" in str(too_high.json())


def test_pause_resume_and_daily_target(client_a, user_a):
    paused = client_a.patch("/api/v1/me/languages/en/", {"is_active": False}, format="json")
    assert paused.status_code == 200 and paused.json()["is_active"] is False
    me = client_a.get("/api/v1/me/").json()
    assert me["languages"][0]["is_active"] is False  # paused profiles stay listed

    target = client_a.patch(
        "/api/v1/me/languages/en/",
        {"default_new_cards_per_day": 2, "is_active": True},
        format="json",
    )
    assert target.status_code == 200
    assert target.json()["default_new_cards_per_day"] == 2 and target.json()["is_active"] is True
    profile = LanguageProfile.all_users.get(user=user_a, language="en")
    assert profile.default_new_cards_per_day == 2 and profile.is_active is True

    too_many = client_a.patch(
        "/api/v1/me/languages/en/", {"default_new_cards_per_day": 999}, format="json"
    )
    assert too_many.status_code == 400

    readonly = client_a.patch(
        "/api/v1/me/languages/en/", {"level": {"rating": 2000}, "code": "fr"}, format="json"
    )
    assert readonly.status_code == 200
    profile.refresh_from_db()
    assert profile.level_rating == 1150 and profile.language == "en"

    assert client_a.get("/api/v1/me/languages/fr/").status_code == 404
    assert client_a.patch("/api/v1/me/languages/fr/", {"is_active": False}).status_code == 404
    assert client_a.delete("/api/v1/me/languages/en/").status_code == 405


def test_profiles_are_isolated(client_a, client_b, user_a, make_profile):
    make_profile(user_a, "fr")
    assert [lang["code"] for lang in client_b.get("/api/v1/me/languages/").json()] == ["en"]
    assert client_b.get("/api/v1/me/languages/fr/").status_code == 404
    assert client_b.patch("/api/v1/me/languages/fr/", {"is_active": False}).status_code == 404
    assert LanguageProfile.all_users.get(user=user_a, language="fr").is_active is True


def test_create_user_command_manages_profiles(db):
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    call_command(
        "create_user",
        "nova@example.com",
        "--password",
        "x",
        "--language",
        "en:1200",
        "--language",
        "fr",
        stdout=out,
    )
    profiles = {
        p.language: p for p in LanguageProfile.all_users.filter(user__email="nova@example.com")
    }
    assert profiles["en"].level_rating == 1200 and profiles["fr"].level_rating == 1150
    assert "en 1200" in out.getvalue() and "fr 1150" in out.getvalue()
    call_command("create_user", "nova@example.com", "--password", "y", "--rating", "1000")
    assert (
        LanguageProfile.all_users.get(user__email="nova@example.com", language="en").level_rating
        == 1000
    )
