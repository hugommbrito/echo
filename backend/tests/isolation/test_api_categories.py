import pytest

pytestmark = pytest.mark.django_db


def test_list_shows_global_and_own_personal_only(client_a, client_b):
    created = client_a.post(
        "/api/v1/categories/",
        {
            "slug": "my-hobbies",
            "name": "My hobbies",
            "description": "Personal",
            "generation_hint": "",
        },
        format="json",
    )
    assert created.status_code == 201, created.content
    assert created.json()["scope"] == "personal"

    slugs_a = {c["slug"]: c["scope"] for c in client_a.get("/api/v1/categories/").json()}
    slugs_b = {c["slug"]: c["scope"] for c in client_b.get("/api/v1/categories/").json()}
    assert slugs_a["my-hobbies"] == "personal"
    assert "my-hobbies" not in slugs_b
    assert slugs_a["job-interview"] == "global" and slugs_b["job-interview"] == "global"


def test_other_user_cannot_read_or_edit_personal_category(client_a, client_b):
    cat = client_a.post(
        "/api/v1/categories/", {"slug": "mine", "name": "Mine"}, format="json"
    ).json()
    assert client_b.get(f"/api/v1/categories/{cat['id']}/").status_code == 404
    assert (
        client_b.patch(
            f"/api/v1/categories/{cat['id']}/", {"name": "Hacked"}, format="json"
        ).status_code
        == 404
    )
    assert client_a.get(f"/api/v1/categories/{cat['id']}/").json()["name"] == "Mine"


def test_global_category_is_read_only_for_users(client_a, global_categories):
    travel = global_categories["travel"]
    response = client_a.patch(f"/api/v1/categories/{travel.id}/", {"name": "X"}, format="json")
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_slug_cannot_collide_with_global_or_own(client_a):
    r1 = client_a.post("/api/v1/categories/", {"slug": "travel", "name": "Travel 2"}, format="json")
    assert r1.status_code == 400 and r1.json()["code"] == "validation_error"
    assert (
        client_a.post(
            "/api/v1/categories/", {"slug": "dup", "name": "Dup"}, format="json"
        ).status_code
        == 201
    )
    assert (
        client_a.post(
            "/api/v1/categories/", {"slug": "dup", "name": "Dup 2"}, format="json"
        ).status_code
        == 400
    )


def test_two_users_may_use_the_same_personal_slug(client_a, client_b):
    assert (
        client_a.post(
            "/api/v1/categories/", {"slug": "same", "name": "A"}, format="json"
        ).status_code
        == 201
    )
    assert (
        client_b.post(
            "/api/v1/categories/", {"slug": "same", "name": "B"}, format="json"
        ).status_code
        == 201
    )


def test_card_count_is_per_user(client_a, client_b, user_a, user_b, make_card, global_categories):
    make_card(user_a, global_categories["travel"])
    make_card(user_a, global_categories["travel"])
    make_card(user_b, global_categories["travel"])
    count_a = {c["slug"]: c["card_count"] for c in client_a.get("/api/v1/categories/").json()}[
        "travel"
    ]
    count_b = {c["slug"]: c["card_count"] for c in client_b.get("/api/v1/categories/").json()}[
        "travel"
    ]
    assert (count_a, count_b) == (2, 1)


def test_anonymous_is_rejected(api_client):
    assert api_client.get("/api/v1/categories/").status_code == 403
