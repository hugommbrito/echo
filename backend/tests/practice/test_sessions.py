import datetime as dt

import pytest
import time_machine

from apps.ai.clients.fake import FakeLLM
from apps.ai.exceptions import AIError
from apps.core.context import owner_context
from apps.practice.models import DailySession, SessionNewCard

pytestmark = pytest.mark.django_db

NOON_UTC = "2026-09-16 15:00:00 +00:00"


def _create(client, category_ids, target):
    return client.post(
        "/api/v1/sessions/",
        {"category_ids": category_ids, "new_cards_target": target},
        format="json",
    )


@time_machine.travel(NOON_UTC, tick=False)
def test_create_session_generates_cards_with_probes_and_round_robin(
    client_a, user_a, global_categories
):
    cats = [global_categories["job-interview"], global_categories["shopping"]]
    response = _create(client_a, [str(c.id) for c in cats], 5)
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["session_date"] == "2026-09-16"
    assert body["status"] == "ready"  # celery eager in tests
    assert body["projected"] == {
        "carried_over": 0,
        "to_generate": 5,
        "due_today": 0,
        "overdue": 0,
        "probes": 1,
        "base_level": "A2",
        "total": 5,
    }
    assert body["progress"] == {
        "new_total": 5,
        "new_done": 0,
        "due_total": 0,
        "due_done": 0,
        "remaining": 5,
    }
    assert body["rating_at_start"] == 1150

    with owner_context(user_a.pk):
        slots = list(
            SessionNewCard.objects.filter(session_id=body["id"])
            .select_related("card", "card__category", "card__scheduler")
            .order_by("position")
        )
    # categories are visited round-robin in their sort_order (shopping=2, job-interview=3)
    assert [s.card.category.slug for s in slots] == [
        "shopping",
        "job-interview",
        "shopping",
        "job-interview",
        "shopping",
    ]
    assert [s.card.cefr_level for s in slots] == ["A2", "A2", "B1", "A2", "A2"]
    assert [s.card.probe for s in slots] == ["none", "none", "above", "none", "none"]
    assert all(s.origin == "generated" and s.card.scheduler.maturity == "new" for s in slots)
    assert all(s.card.difficulty_rating in {1240, 1300, 1360, 1040, 1100, 1160} for s in slots)
    assert len(FakeLLM.calls) == 1 and "job-interview — level: A2" in FakeLLM.calls[0]["user"]


@time_machine.travel(NOON_UTC, tick=False)
def test_second_session_same_day_conflicts(client_a, global_categories):
    ids = [str(global_categories["travel"].id)]
    first = _create(client_a, ids, 2).json()
    second = _create(client_a, ids, 2)
    assert second.status_code == 409
    assert second.json()["code"] == "session_exists"
    assert second.json()["session_id"] == first["id"]


@time_machine.travel(NOON_UTC, tick=False)
def test_today_endpoint(client_a, global_categories):
    missing = client_a.get("/api/v1/sessions/today/")
    assert missing.status_code == 404 and missing.json()["code"] == "no_session_today"
    created = _create(client_a, [str(global_categories["travel"].id)], 1).json()
    assert client_a.get("/api/v1/sessions/today/").json()["id"] == created["id"]


def test_session_date_follows_user_timezone(client_a, user_a, global_categories):
    with time_machine.travel(
        "2026-09-17 01:30:00 +00:00", tick=False
    ):  # 22:30 in São Paulo on the 16th
        body = _create(client_a, [str(global_categories["travel"].id)], 1).json()
    assert body["session_date"] == "2026-09-16"


@time_machine.travel(NOON_UTC, tick=False)
def test_projection_endpoint(client_a, user_a, make_card, global_categories):
    make_card(
        user_a, maturity="learning", due_date=dt.date(2026, 9, 10), interval_days=1
    )  # overdue
    make_card(user_a, maturity="learning", due_date=dt.date(2026, 9, 16), interval_days=6)
    make_card(user_a, maturity="mature", due_date=dt.date(2026, 10, 1), interval_days=30)
    make_card(user_a)  # new -> carried over
    travel = str(global_categories["travel"].id)
    body = client_a.get(
        f"/api/v1/sessions/projection/?new_cards_target=5&category_ids={travel}"
    ).json()
    assert body == {
        "carried_over": 1,
        "to_generate": 4,
        "due_today": 2,
        "overdue": 1,
        "probes": 1,
        "base_level": "A2",
        "total": 7,
    }
    no_categories = client_a.get("/api/v1/sessions/projection/?new_cards_target=5").json()
    assert no_categories["to_generate"] == 0 and no_categories["carried_over"] == 1


def test_carry_over_next_day_without_generation(client_a, user_a, global_categories):
    ids = [str(global_categories["travel"].id)]
    with time_machine.travel(NOON_UTC, tick=False):
        day1 = _create(client_a, ids, 3).json()
    assert day1["status"] == "ready" and len(FakeLLM.calls) == 1
    with time_machine.travel("2026-09-17 15:00:00 +00:00", tick=False):
        day2 = _create(client_a, ids, 3)
    assert day2.status_code == 201
    body = day2.json()
    assert body["session_date"] == "2026-09-17"
    assert body["status"] == "ready"
    assert body["projected"]["carried_over"] == 3 and body["projected"]["to_generate"] == 0
    assert len(FakeLLM.calls) == 1  # nothing generated on day 2
    with owner_context(user_a.pk):
        origins = list(
            SessionNewCard.objects.filter(session_id=body["id"]).values_list("origin", flat=True)
        )
    assert origins == ["carried_over"] * 3
    queue = client_a.get(f"/api/v1/sessions/{body['id']}/queue/").json()
    assert [i["origin"] for i in queue] == ["carried_over"] * 3
    # levels are the ones chosen on day 1 (2 at the base band + 1 probe), never recalculated
    assert sorted(i["card"]["cefr_level"] for i in queue) == ["A2", "A2", "B1"]


@time_machine.travel(NOON_UTC, tick=False)
def test_queue_new_first_then_due_by_date_and_ease(client_a, user_a, make_card, global_categories):
    late_easy = make_card(
        user_a,
        question="late easy",
        maturity="learning",
        due_date=dt.date(2026, 9, 10),
        ease="2.50",
    )
    late_hard = make_card(
        user_a,
        question="late hard",
        maturity="learning",
        due_date=dt.date(2026, 9, 10),
        ease="1.80",
    )
    today_due = make_card(
        user_a, question="today", maturity="mature", due_date=dt.date(2026, 9, 16)
    )
    make_card(user_a, question="future", maturity="mature", due_date=dt.date(2026, 9, 20))
    make_card(
        user_a,
        question="suspended",
        maturity="learning",
        due_date=dt.date(2026, 9, 1),
        status="suspended",
    )
    session = _create(client_a, [str(global_categories["travel"].id)], 2).json()
    items = client_a.get(f"/api/v1/sessions/{session['id']}/queue/").json()
    assert [i["kind"] for i in items] == ["new", "new", "due", "due", "due"]
    assert [i["position"] for i in items[:2]] == [1, 2]
    assert [i["card"]["id"] for i in items[2:]] == [
        str(late_hard.id),
        str(late_easy.id),
        str(today_due.id),
    ]
    assert items[2]["due_date"] == "2026-09-10"
    first = client_a.get(f"/api/v1/sessions/{session['id']}/queue/?limit=1").json()
    assert len(first) == 1 and first[0]["kind"] == "new"
    progress = client_a.get(f"/api/v1/sessions/{session['id']}/").json()["progress"]
    assert progress == {
        "new_total": 2,
        "new_done": 0,
        "due_total": 3,
        "due_done": 0,
        "remaining": 5,
    }


@time_machine.travel(NOON_UTC, tick=False)
def test_generation_failure_and_retry(client_a, user_a, global_categories):
    FakeLLM.fail_next = AIError("provider down")
    body = _create(client_a, [str(global_categories["travel"].id)], 3).json()
    assert body["status"] == "failed" and "provider down" in body["generation_error"]
    retried = client_a.post(f"/api/v1/sessions/{body['id']}/retry-generation/")
    assert retried.status_code == 200
    assert retried.json()["status"] == "ready"
    assert retried.json()["progress"]["new_total"] == 3
    again = client_a.post(f"/api/v1/sessions/{body['id']}/retry-generation/")
    assert again.status_code == 409 and again.json()["code"] == "not_failed"


@time_machine.travel(NOON_UTC, tick=False)
def test_validation_errors(client_a, global_categories, user_b):
    assert _create(client_a, [], 3).status_code == 400
    assert _create(client_a, [str(global_categories["travel"].id)], 999).status_code == 400
    personal_of_b = client_b_category(user_b)
    response = _create(client_a, [str(personal_of_b.id)], 1)
    assert response.status_code == 400 and "Unknown or inactive" in str(response.json())


def client_b_category(user_b):
    from apps.cards.models import Category

    return Category.objects.create(owner=user_b, slug="secret", name="Secret")


@time_machine.travel(NOON_UTC, tick=False)
def test_sessions_are_isolated(client_a, client_b, global_categories):
    session = _create(client_a, [str(global_categories["travel"].id)], 1).json()
    assert client_b.get(f"/api/v1/sessions/{session['id']}/").status_code == 404
    assert client_b.get(f"/api/v1/sessions/{session['id']}/queue/").status_code == 404
    assert client_b.get("/api/v1/sessions/today/").status_code == 404
    assert client_b.get("/api/v1/sessions/").json()["count"] == 0


def test_session_history_filter(client_a, global_categories):
    ids = [str(global_categories["travel"].id)]
    with time_machine.travel("2026-09-10 15:00:00 +00:00", tick=False):
        _create(client_a, ids, 1)
    with time_machine.travel(NOON_UTC, tick=False):
        _create(client_a, ids, 1)
    assert client_a.get("/api/v1/sessions/").json()["count"] == 2
    assert client_a.get("/api/v1/sessions/?from=2026-09-15").json()["count"] == 1
    assert client_a.get("/api/v1/sessions/?to=2026-09-12").json()["count"] == 1
    assert DailySession.all_users.count() == 2
