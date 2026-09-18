"""Numbers are checked against a hand-built dataset (see `dataset`)."""

import datetime as dt
from decimal import Decimal

import pytest
import time_machine
from django.core.files.base import ContentFile

from apps.core.context import owner_context
from apps.leveling.services import apply_level_result
from apps.practice.models import Attempt, Evaluation
from apps.scheduling import sm2
from apps.scheduling.services import apply_review

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 9, 16)
NOW = "2026-09-16 15:00:00 +00:00"


def answer(
    user,
    card,
    on: dt.date,
    scores: tuple[int, int, int],
    *,
    counts=True,
    issues=None,
    duration=60,
    insufficient=False,
):
    """Create a completed attempt with an evaluation and, if it counts, apply SM-2 + ELO."""
    with owner_context(user.pk):
        number = Attempt.objects.filter(card=card).count() + 1
        attempt = Attempt(
            user=user,
            card=card,
            attempt_number=number,
            attempted_on=on,
            audio_mime="audio/webm",
            audio_size_bytes=10,
            audio_duration_seconds=Decimal(duration),
            status="completed",
            transcript_text="x " * 40,
            word_count=40,
            words_per_minute=Decimal("80.0"),
            insufficient_speech=insufficient,
            completed_at=dt.datetime(on.year, on.month, on.day, 12, tzinfo=dt.UTC),
        )
        attempt.audio_file.save(f"{attempt.id}.webm", ContentFile(b"x"), save=False)
        attempt.save()
        composite = sm2.composite_score(*scores)
        Evaluation.objects.create(
            user=user,
            attempt=attempt,
            structure_score=scores[0],
            grammar_score=scores[1],
            fluency_score=scores[2],
            grammar_issues=issues or [],
            fluency_markers={"fillers": 1, "false_starts": 0, "repetitions": 0},
            composite_score=composite,
            sm2_quality=sm2.quality_from_composite(composite, scores[0]),
            model="test",
            prompt_version="v1",
        )
        if counts and not insufficient:
            apply_review(
                card=card,
                attempt=attempt,
                composite=composite,
                quality=sm2.quality_from_composite(composite, scores[0]),
                reviewed_on=on,
            )
            apply_level_result(
                user=user, card=card, attempt=attempt, composite=composite, logged_on=on
            )
            attempt.counts_for_scheduling = True
            attempt.save(update_fields=["counts_for_scheduling"])
    return attempt


@pytest.fixture
def dataset(user_a, user_b, make_card, global_categories):
    ji, travel = global_categories["job-interview"], global_categories["travel"]
    c1 = make_card(user_a, ji, question="c1", level="A2", difficulty_rating=1100)
    c2 = make_card(user_a, travel, question="c2", level="B1", difficulty_rating=1300, probe="above")
    c3 = make_card(user_a, ji, question="c3", level="A2", difficulty_rating=1100)
    make_card(user_a, travel, question="never answered")  # new, in the collection
    make_card(user_a, travel, question="suspended", status="suspended")
    # 40 days ago (previous period): one answer
    answer(
        user_a,
        c1,
        TODAY - dt.timedelta(days=40),
        (3, 3, 3),
        issues=[{"type": "article", "quote": "a", "correction": "the"}],
    )
    # in the period
    answer(
        user_a,
        c1,
        TODAY - dt.timedelta(days=10),
        (4, 3, 3),
        issues=[
            {"type": "verb_tense", "quote": "I go", "correction": "I went"},
            {"type": "article", "quote": "a", "correction": "the"},
        ],
    )
    answer(
        user_a,
        c2,
        TODAY - dt.timedelta(days=3),
        (5, 4, 4),
        issues=[{"type": "verb_tense", "quote": "she go", "correction": "she goes"}],
    )
    answer(user_a, c3, TODAY, (2, 2, 2))
    answer(user_a, c3, TODAY, (4, 4, 4), counts=False)  # second attempt today: stats only
    answer(user_a, c3, TODAY, (1, 1, 1), insufficient=True)  # excluded from score averages
    # noise for user B
    cb = make_card(user_b, ji, question="b1")
    answer(user_b, cb, TODAY, (5, 5, 5))
    return {"c1": c1, "c2": c2, "c3": c3}


@time_machine.travel(NOW, tick=False)
def test_overview(client_a, user_a, dataset):
    body = client_a.get("/api/v1/stats/overview/").json()
    assert body["period"] == {"from": "2026-08-18", "to": "2026-09-16", "days": 30}
    assert (
        body["today"]["answered"] == 1
        and body["today"]["new_answered"] == 1
        and body["today"]["due_answered"] == 0
    )
    assert body["today"]["target"] == 3
    assert body["collection"] == {"total": 4, "new": 1, "learning": 3, "mature": 0, "suspended": 1}
    # c1 due 6 days after 09-06 = 09-12 (overdue); c2 due 09-14 (overdue); c3 due 09-17
    assert body["due"] == {"today": 2, "overdue": 2, "next_7_days": 1}
    scores = body["scores"]["period"]
    assert scores["attempts"] == 4
    assert scores["structure_avg"] == 3.75  # (4+5+2+4)/4
    assert scores["grammar_avg"] == 3.25
    assert scores["fluency_avg"] == 3.25
    assert body["scores"]["previous_period"]["attempts"] == 1
    user_a.refresh_from_db()
    assert body["level"]["rating"] == user_a.level_rating
    assert body["level"]["counted_attempts"] == 4
    assert (
        body["level"]["delta_period"] == user_a.level_rating - 1147
    )  # first counted attempt moved 1150 -> 1147
    assert body["level"]["next_band"]["label"] == "B1"


@time_machine.travel(NOW, tick=False)
def test_scores_by_day_and_week(client_a, dataset):
    days = client_a.get("/api/v1/stats/scores/?bucket=day").json()
    assert [d["bucket_start"] for d in days] == ["2026-09-06", "2026-09-13", "2026-09-16"]
    assert days[-1] == {
        "bucket_start": "2026-09-16",
        "structure_avg": 3.0,
        "grammar_avg": 3.0,
        "fluency_avg": 3.0,
        "composite_avg": 3.0,
        "attempts": 2,
    }
    weeks = client_a.get("/api/v1/stats/scores/?bucket=week").json()
    assert [w["bucket_start"] for w in weeks] == ["2026-08-31", "2026-09-07", "2026-09-14"]
    assert weeks[2]["attempts"] == 2  # both 09-16 attempts; 09-13 belongs to the week of 09-07
    filtered = client_a.get("/api/v1/stats/scores/?bucket=day&category=travel").json()
    assert len(filtered) == 1 and filtered[0]["attempts"] == 1
    assert client_a.get("/api/v1/stats/scores/?category=nope").status_code == 400
    assert client_a.get("/api/v1/stats/scores/?bucket=month").status_code == 400


@time_machine.travel(NOW, tick=False)
def test_level_series_and_probes(client_a, user_a, dataset):
    body = client_a.get("/api/v1/stats/level/").json()
    assert body["points"][0] == {"date": "2026-08-18", "rating_after": 1147}
    assert [p["date"] for p in body["points"][1:]] == ["2026-09-06", "2026-09-13", "2026-09-16"]
    user_a.refresh_from_db()
    assert body["points"][-1]["rating_after"] == user_a.level_rating == body["current"]["rating"]
    assert body["probes"]["above"] == {
        "answered": 1,
        "hits": 1,
        "avg_actual": 0.85,
        "avg_delta": body["probes"]["above"]["avg_delta"],
    }
    assert body["probes"]["below"]["answered"] == 0
    assert len(body["bands"]) == 6 and body["bands"][1]["label"] == "A2"
    assert body["events"][0]["probe"] == "above" and body["events"][0]["hit"] is True


@time_machine.travel(NOW, tick=False)
def test_activity_forecast_collection(client_a, dataset):
    activity = client_a.get("/api/v1/stats/activity/?bucket=day").json()
    assert activity[-1] == {
        "bucket_start": "2026-09-16",
        "new": 1,
        "learning": 0,
        "mature": 0,
        "total": 1,
        "speaking_seconds": 180,
    }
    forecast = client_a.get("/api/v1/stats/forecast/?days=7").json()
    assert forecast["overdue"] == 2 and forecast["total"] == 3
    assert forecast["days"][0] == {"date": "2026-09-16", "due": 2} and forecast["days"][1] == {
        "date": "2026-09-17",
        "due": 1,
    }
    collection = client_a.get("/api/v1/stats/collection/").json()
    assert collection["by_maturity"] == {"new": 1, "learning": 3, "mature": 0, "suspended": 1}
    assert {c["category"]["slug"]: c["total"] for c in collection["by_category"]} == {
        "job-interview": 2,
        "travel": 2,
    }
    assert {row["level"]: row["count"] for row in collection["by_level"]}["A2"] == 2


@time_machine.travel(NOW, tick=False)
def test_grammar_issues_and_categories(client_a, dataset):
    issues = client_a.get("/api/v1/stats/grammar-issues/").json()
    assert issues["total"] == 3 and issues["previous_total"] == 1
    by_type = {i["type"]: i for i in issues["items"]}
    assert by_type["verb_tense"]["count"] == 2 and by_type["verb_tense"]["delta"] == 2
    assert by_type["article"] == {
        "type": "article",
        "count": 1,
        "previous_count": 1,
        "delta": 0,
        "examples": [{"quote": "a", "correction": "the"}],
    }
    cats = client_a.get("/api/v1/stats/categories/").json()
    rows = {c["category"]["slug"]: c for c in cats}
    assert rows["job-interview"]["cards"] == 2 and rows["job-interview"]["attempts"] == 3
    assert rows["travel"]["attempts"] == 1 and rows["travel"]["composite_avg"] == 4.4
    assert len(rows["job-interview"]["trend"]) == 2


@time_machine.travel(NOW, tick=False)
def test_heatmap_and_advanced(client_a, dataset):
    heat = client_a.get("/api/v1/stats/heatmap/?year=2026").json()
    assert {h["date"]: h["count"] for h in heat} == {
        "2026-08-07": 1,
        "2026-09-06": 1,
        "2026-09-13": 1,
        "2026-09-16": 3,
    }
    adv = client_a.get("/api/v1/stats/advanced/").json()
    assert sum(i["count"] for i in adv["intervals"]) == 3
    assert adv["answer_duration"]["attempts"] == 6 and adv["answer_duration"]["avg_seconds"] == 60


@time_machine.travel(NOW, tick=False)
def test_stats_are_isolated(client_b, dataset):
    body = client_b.get("/api/v1/stats/overview/").json()
    assert body["collection"]["total"] == 1 and body["scores"]["period"]["attempts"] == 1
    assert client_b.get("/api/v1/stats/grammar-issues/").json()["total"] == 0
