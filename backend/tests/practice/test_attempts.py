import datetime as dt
from decimal import Decimal

import pytest
import time_machine

from apps.accounts.models import LanguageProfile
from apps.ai.clients.fake import FakeLLM, FakeProbe, FakeTranscriber
from apps.ai.exceptions import TranscriptionError
from apps.ai.models import AIRequestLog
from apps.core.context import owner_context
from apps.leveling.models import LevelLog
from apps.scheduling.models import ReviewLog

pytestmark = pytest.mark.django_db

NOON_UTC = "2026-09-16 15:00:00 +00:00"
GOOD_TRANSCRIPT = (
    "Last year I worked in a store in my city. One day a customer was angry because her order was "
    "late. I listened to her, I apologised and I offered a discount. In the end she was happy and "
    "she came back the next week, so I think I handled it well."
)


def _upload(client, card, audio, session_id=None, **extra):
    data = {
        "card_id": str(card.id),
        "audio": audio,
        "mime_type": "audio/webm",
        "duration_seconds": "31.5",
        **extra,
    }
    if session_id:
        data["session_id"] = str(session_id)
    return client.post("/api/v1/attempts/", data, format="multipart")


@time_machine.travel(NOON_UTC, tick=False)
def test_full_pipeline_moves_scheduler_and_rating(
    client_a, user_a, make_card, audio_file, global_categories
):
    card = make_card(
        user_a, global_categories["job-interview"], level="B1", difficulty_rating=1300
    )  # probe above for an A2 learner
    FakeTranscriber.queue(GOOD_TRANSCRIPT)
    accepted = _upload(client_a, card, audio_file())
    assert accepted.status_code == 202, accepted.content
    attempt_id = accepted.json()["id"]

    body = client_a.get(f"/api/v1/attempts/{attempt_id}/").json()
    assert body["status"] == "completed", body
    assert body["attempt_number"] == 1 and body["counts_for_scheduling"] is True
    assert body["audio_duration_seconds"] == "30.00"  # from the (fake) probe, not the client timer
    assert body["word_count"] == len(GOOD_TRANSCRIPT.split())
    assert body["words_per_minute"] == str(round(len(GOOD_TRANSCRIPT.split()) / 0.5, 1))
    assert body["audio_url"].startswith("/media/users/") and str(user_a.id) in body["audio_url"]

    ev = body["evaluation"]
    assert set(ev) >= {
        "structure",
        "grammar",
        "fluency",
        "composite_score",
        "sm2_quality",
        "key_points",
        "improved_answer",
    }
    assert ev["improved_answer"] is None
    assert ev["key_points"] == card.key_points
    scores = (ev["structure"]["score"], ev["grammar"]["score"], ev["fluency"]["score"])
    composite = Decimal(ev["composite_score"])
    assert composite == (
        Decimal("0.40") * scores[0] + Decimal("0.35") * scores[1] + Decimal("0.25") * scores[2]
    ).quantize(Decimal("0.01"))

    review = body["review"]
    assert review["maturity_before"] == "new" and review["maturity_after"] == "learning"
    assert review["interval_after"] == 1 and review["due_after"] == "2026-09-17"

    change = body["level_change"]
    assert (
        change["rating_before"] == 1150
        and change["question_rating"] == 1300
        and change["k_factor"] == 40
    )
    assert change["rating_after"] == 1150 + change["delta"]
    assert body["language"] == "en"
    profile = LanguageProfile.all_users.get(user=user_a, language="en")
    assert profile.level_rating == change["rating_after"] and profile.counted_attempts == 1
    with owner_context(user_a.pk):
        assert ReviewLog.objects.count() == 1 and LevelLog.objects.count() == 1
        assert LevelLog.objects.get().language == "en"
        kinds = list(AIRequestLog.objects.order_by("created_at").values_list("kind", "language"))
    assert kinds == [("transcribe", "en"), ("evaluate", "en")]
    assert FakeTranscriber.calls[-1]["language"] == "en"
    assert FakeTranscriber.calls[-1]["prompt"].startswith("Um, uh")
    me = client_a.get("/api/v1/me/").json()["languages"][0]["level"]
    assert me["rating"] == change["rating_after"] and me["counted_attempts"] == 1


@time_machine.travel(NOON_UTC, tick=False)
def test_second_attempt_same_day_is_recorded_but_does_not_count(
    client_a, user_a, make_card, audio_file
):
    card = make_card(user_a)
    FakeTranscriber.queue(GOOD_TRANSCRIPT)
    first = client_a.get(
        f"/api/v1/attempts/{_upload(client_a, card, audio_file()).json()['id']}/"
    ).json()
    FakeTranscriber.queue(GOOD_TRANSCRIPT + " And I learned a lot from that day, honestly.")
    second = client_a.get(
        f"/api/v1/attempts/{_upload(client_a, card, audio_file()).json()['id']}/"
    ).json()
    assert (first["attempt_number"], second["attempt_number"]) == (1, 2)
    assert first["counts_for_scheduling"] is True and second["counts_for_scheduling"] is False
    assert second["review"] is None and second["level_change"] is None
    assert second["evaluation"] is not None
    assert LanguageProfile.all_users.get(user=user_a, language="en").counted_attempts == 1
    history = client_a.get(f"/api/v1/cards/{card.id}/history/").json()
    assert [h["attempt_number"] for h in history] == [2, 1]
    detail = client_a.get(f"/api/v1/cards/{card.id}/").json()
    assert detail["attempt_count"] == 2 and detail["last_scores"]["attempt_id"] == second["id"]


@time_machine.travel(NOON_UTC, tick=False)
def test_insufficient_speech_scores_one_and_keeps_card_new(
    client_a, user_a, make_card, audio_file, global_categories
):
    session = client_a.post(
        "/api/v1/sessions/",
        {"category_ids": [str(global_categories["travel"].id)], "new_cards_targets": {"en": 1}},
        format="json",
    ).json()
    card_id = client_a.get(f"/api/v1/sessions/{session['id']}/queue/").json()[0]["card"]["id"]
    FakeTranscriber.queue("Hello there")
    from apps.cards.models import Card

    card = Card.all_users.get(pk=card_id)
    body = client_a.get(
        f"/api/v1/attempts/{_upload(client_a, card, audio_file(), session['id']).json()['id']}/"
    ).json()
    assert body["status"] == "completed"
    assert body["insufficient_speech"] is True and body["counts_for_scheduling"] is False
    ev = body["evaluation"]
    assert (ev["structure"]["score"], ev["grammar"]["score"], ev["fluency"]["score"]) == (1, 1, 1)
    assert "fala suficiente" in ev["structure"]["feedback"]
    assert body["review"] is None and body["level_change"] is None
    assert (
        len([c for c in FakeLLM.calls if c["output_format"] == "EvaluationOutput"]) == 0
    )  # no tokens spent
    # the card is still in today's queue and the session is still in progress
    queue = client_a.get(f"/api/v1/sessions/{session['id']}/queue/").json()
    assert [i["card"]["id"] for i in queue] == [card_id]
    assert client_a.get(f"/api/v1/sessions/{session['id']}/").json()["status"] == "in_progress"
    improved = client_a.post(f"/api/v1/attempts/{body['id']}/improved-answer/")
    assert improved.status_code == 409 and improved.json()["code"] == "insufficient_speech"


@time_machine.travel(NOON_UTC, tick=False)
def test_session_completes_when_queue_empties(
    client_a, user_a, make_card, audio_file, global_categories
):
    session = client_a.post(
        "/api/v1/sessions/",
        {"category_ids": [str(global_categories["travel"].id)], "new_cards_targets": {"en": 1}},
        format="json",
    ).json()
    card_id = client_a.get(f"/api/v1/sessions/{session['id']}/queue/").json()[0]["card"]["id"]
    from apps.cards.models import Card

    FakeTranscriber.queue(GOOD_TRANSCRIPT)
    _upload(client_a, Card.all_users.get(pk=card_id), audio_file(), session["id"])
    body = client_a.get(f"/api/v1/sessions/{session['id']}/").json()
    assert body["status"] == "completed" and body["completed_at"] is not None
    assert body["progress"] == {
        "new_total": 1,
        "new_done": 1,
        "due_total": 0,
        "due_done": 0,
        "remaining": 0,
    }
    assert client_a.get(f"/api/v1/sessions/{session['id']}/queue/").json() == []


@time_machine.travel(NOON_UTC, tick=False)
def test_due_card_review_counts_in_progress(
    client_a, user_a, make_card, audio_file, global_categories
):
    due = make_card(
        user_a, maturity="learning", due_date=dt.date(2026, 9, 15), interval_days=6, repetitions=2
    )
    session = client_a.post(
        "/api/v1/sessions/", {"category_ids": [], "new_cards_targets": {"en": 0}}, format="json"
    ).json()
    assert session["status"] == "ready" and session["progress"]["due_total"] == 1
    FakeTranscriber.queue(GOOD_TRANSCRIPT)
    body = client_a.get(
        f"/api/v1/attempts/{_upload(client_a, due, audio_file(), session['id']).json()['id']}/"
    ).json()
    assert body["review"]["maturity_before"] == "learning"
    assert body["review"]["interval_before"] == 6
    progress = client_a.get(f"/api/v1/sessions/{session['id']}/").json()["progress"]
    assert progress == {
        "new_total": 0,
        "new_done": 0,
        "due_total": 1,
        "due_done": 1,
        "remaining": 0,
    }


@time_machine.travel(NOON_UTC, tick=False)
def test_probe_rejects_out_of_range_or_corrupt_audio(client_a, user_a, make_card, audio_file):
    card = make_card(user_a)
    FakeProbe.queue(1.2)
    short = client_a.get(
        f"/api/v1/attempts/{_upload(client_a, card, audio_file()).json()['id']}/"
    ).json()
    assert (
        short["status"] == "failed"
        and short["failure_stage"] == "probing"
        and "too short" in short["error_message"]
    )
    FakeProbe.queue(400.0)
    long_ = client_a.get(
        f"/api/v1/attempts/{_upload(client_a, card, audio_file()).json()['id']}/"
    ).json()
    assert long_["failure_stage"] == "probing" and "too long" in long_["error_message"]
    assert short["review"] is None and len(FakeLLM.calls) == 0
    assert LanguageProfile.all_users.get(user=user_a, language="en").counted_attempts == 0


@time_machine.travel(NOON_UTC, tick=False)
def test_transcription_failure_then_retry_resumes(client_a, user_a, make_card, audio_file):
    card = make_card(user_a)
    FakeTranscriber.fail_next = TranscriptionError("openai 503")
    attempt_id = _upload(client_a, card, audio_file()).json()["id"]
    failed = client_a.get(f"/api/v1/attempts/{attempt_id}/").json()
    assert failed["status"] == "failed" and failed["failure_stage"] == "transcribing"
    assert failed["audio_duration_seconds"] == "30.00"  # probe result kept for the retry
    FakeProbe.queue(AssertionError("probe must not run again"))
    FakeTranscriber.queue(GOOD_TRANSCRIPT)
    retried = client_a.post(f"/api/v1/attempts/{attempt_id}/retry/")
    assert retried.status_code == 200, retried.content
    assert retried.json()["status"] == "completed" and retried.json()["failure_stage"] == ""
    assert retried.json()["counts_for_scheduling"] is True
    with owner_context(user_a.pk):
        statuses = list(AIRequestLog.objects.order_by("created_at").values_list("kind", "status"))
    assert statuses == [("transcribe", "error"), ("transcribe", "ok"), ("evaluate", "ok")]
    not_failed = client_a.post(f"/api/v1/attempts/{attempt_id}/retry/")
    assert not_failed.status_code == 409


@time_machine.travel(NOON_UTC, tick=False)
def test_improved_answer_generated_once_and_cached(client_a, user_a, make_card, audio_file):
    card = make_card(user_a)
    FakeTranscriber.queue("So um I have work there for two years and " + GOOD_TRANSCRIPT)
    attempt_id = _upload(client_a, card, audio_file()).json()["id"]
    before = len(FakeLLM.calls)
    first = client_a.post(f"/api/v1/attempts/{attempt_id}/improved-answer/")
    assert first.status_code == 200, first.content
    assert "I have worked there" in first.json()["improved_answer"]
    assert first.json()["notes"] and first.json()["model"] == "claude-sonnet-5"
    second = client_a.post(f"/api/v1/attempts/{attempt_id}/improved-answer/")
    assert second.json() == first.json()
    assert len(FakeLLM.calls) == before + 1
    assert (
        client_a.get(f"/api/v1/attempts/{attempt_id}/").json()["evaluation"]["improved_answer"]
        == first.json()["improved_answer"]
    )
    with owner_context(user_a.pk):
        assert AIRequestLog.objects.filter(kind="improve_answer").count() == 1


@time_machine.travel(NOON_UTC, tick=False)
def test_upload_validation(client_a, user_a, make_card, audio_file):
    card = make_card(user_a)
    empty = client_a.post(
        "/api/v1/attempts/",
        {"card_id": str(card.id), "audio": audio_file(size=0)},
        format="multipart",
    )
    assert empty.status_code == 400
    wrong_type = client_a.post(
        "/api/v1/attempts/",
        {
            "card_id": str(card.id),
            "audio": audio_file(name="x.txt", content_type="text/plain"),
            "mime_type": "text/plain",
        },
        format="multipart",
    )
    assert wrong_type.status_code == 400
    suspended = make_card(user_a, status="suspended")
    assert _upload(client_a, suspended, audio_file()).status_code == 409


@time_machine.travel(NOON_UTC, tick=False)
def test_attempts_are_isolated(client_a, client_b, user_a, make_card, audio_file):
    card = make_card(user_a)
    FakeTranscriber.queue(GOOD_TRANSCRIPT)
    attempt_id = _upload(client_a, card, audio_file()).json()["id"]
    assert client_b.get(f"/api/v1/attempts/{attempt_id}/").status_code == 404
    assert client_b.post(f"/api/v1/attempts/{attempt_id}/improved-answer/").status_code == 404
    assert client_b.get(f"/api/v1/attempts/{attempt_id}/audio/").status_code == 404
    forged = _upload(client_b, card, audio_file())
    assert forged.status_code == 400 and "Unknown card" in str(forged.json())
    assert client_b.get(f"/api/v1/cards/{card.id}/history/").status_code == 404
    audio = client_a.get(f"/api/v1/attempts/{attempt_id}/audio/")
    assert (
        audio.status_code == 302 and f"users/{user_a.id}/attempts/{attempt_id}" in audio["Location"]
    )
