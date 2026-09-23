import datetime as dt

import pytest

pytestmark = pytest.mark.django_db


def test_list_and_filters(client_a, user_a, make_card, global_categories):
    make_card(user_a, global_categories["travel"], question="Where did you fly last?", level="A2")
    make_card(
        user_a,
        global_categories["job-interview"],
        question="Tell me about yourself.",
        level="B1",
        maturity="learning",
        due_date=dt.date(2026, 9, 20),
        interval_days=6,
    )
    make_card(
        user_a,
        global_categories["job-interview"],
        question="Why this job?",
        level="B1",
        status="suspended",
    )

    make_card(
        user_a,
        global_categories["shopping"],
        question="Racontez-moi la dernière fois que vous avez magasiné.",
        level="A1",
        language="fr",
    )

    body = client_a.get("/api/v1/cards/").json()
    assert body["count"] == 4
    assert {c["maturity"] for c in body["results"]} == {"new", "learning"}
    assert {c["language"] for c in body["results"]} == {"en", "fr"}
    assert client_a.get("/api/v1/cards/?language=fr").json()["count"] == 1
    assert client_a.get("/api/v1/cards/?language=en").json()["count"] == 3

    assert client_a.get("/api/v1/cards/?category=job-interview").json()["count"] == 2
    assert client_a.get("/api/v1/cards/?maturity=learning").json()["count"] == 1
    assert client_a.get("/api/v1/cards/?level=A2").json()["count"] == 1
    assert client_a.get("/api/v1/cards/?status=suspended").json()["count"] == 1
    assert client_a.get("/api/v1/cards/?q=fly").json()["count"] == 1
    assert (
        client_a.get(f"/api/v1/cards/?category={global_categories['travel'].id}").json()["count"]
        == 1
    )


def test_detail_includes_scheduler(client_a, user_a, make_card):
    card = make_card(
        user_a, maturity="learning", due_date=dt.date(2026, 9, 20), interval_days=6, repetitions=2
    )
    body = client_a.get(f"/api/v1/cards/{card.id}/").json()
    assert body["scheduler"]["maturity"] == "learning"
    assert body["scheduler"]["due_date"] == "2026-09-20"
    assert body["scheduler"]["interval_days"] == 6
    assert body["last_scores"] is None
    assert body["attempt_count"] == 0
    assert body["category"]["scope"] == "global"


def test_suspend_and_unsuspend(client_a, user_a, make_card):
    card = make_card(user_a)
    assert client_a.post(f"/api/v1/cards/{card.id}/suspend/").json()["status"] == "suspended"
    card.refresh_from_db()
    assert card.status == "suspended"
    assert client_a.post(f"/api/v1/cards/{card.id}/unsuspend/").json()["status"] == "active"


def test_cards_are_isolated_between_users(client_a, client_b, user_a, user_b, make_card):
    card_a = make_card(user_a)
    make_card(user_b)
    assert client_a.get("/api/v1/cards/").json()["count"] == 1
    assert client_b.get(f"/api/v1/cards/{card_a.id}/").status_code == 404
    assert client_b.post(f"/api/v1/cards/{card_a.id}/suspend/").status_code == 404
    card_a.refresh_from_db()
    assert card_a.status == "active"


def test_cards_are_read_only_via_api(client_a, user_a, make_card):
    card = make_card(user_a)
    assert (
        client_a.patch(
            f"/api/v1/cards/{card.id}/", {"question_text": "x"}, format="json"
        ).status_code
        == 405
    )
    assert client_a.delete(f"/api/v1/cards/{card.id}/").status_code == 405
    assert client_a.post("/api/v1/cards/", {"question_text": "x"}, format="json").status_code == 405
