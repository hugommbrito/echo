"""Attempt pipeline (§4.6): probing -> transcribing -> evaluating -> scheduling -> completed.

Idempotent per stage: a retry skips stages whose outputs already exist.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import LanguageProfile
from apps.ai import services as ai_services
from apps.ai.clients import get_prober
from apps.ai.exceptions import AIError, AudioProbeError, TranscriptionError
from apps.leveling.services import apply_level_result
from apps.practice.models import Attempt, AttemptStatus, Evaluation
from apps.practice.services import refresh_status
from apps.scheduling import sm2
from apps.scheduling.services import apply_review

log = logging.getLogger("echo.pipeline")

INSUFFICIENT_SPEECH_FEEDBACK = {
    "pt-BR": "Não detectamos fala suficiente para avaliar. Tente gravar de novo.",
    "en": "We could not detect enough speech to evaluate. Please record again.",
}


class StageError(Exception):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.message = message


@contextmanager
def local_copy(attempt: Attempt):
    suffix = Path(attempt.audio_file.name).suffix or ".bin"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        path = Path(tmp.name)
        try:
            with attempt.audio_file.open("rb") as src:
                shutil.copyfileobj(src, tmp)
        except FileNotFoundError as exc:
            path.unlink(missing_ok=True)
            raise StageError("probing", f"Audio file not found in storage: {exc}") from exc
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def _set_status(attempt: Attempt, status: str) -> None:
    attempt.status = status
    attempt.save(update_fields=["status", "updated_at"])


def _fail(attempt: Attempt, stage: str, message: str) -> None:
    attempt.status = AttemptStatus.FAILED
    attempt.failure_stage = stage
    attempt.error_message = message[:2000]
    attempt.save(update_fields=["status", "failure_stage", "error_message", "updated_at"])
    log.warning("attempt %s failed at %s: %s", attempt.id, stage, message)


def run(attempt_id) -> Attempt:
    attempt = Attempt.objects.select_related(
        "card", "card__category", "card__scheduler", "session", "user"
    ).get(pk=attempt_id)
    if attempt.status == AttemptStatus.COMPLETED:
        return attempt
    try:
        with local_copy(attempt) as path:
            if attempt.audio_duration_seconds is None:
                stage_probe(attempt, path)
            if not attempt.transcript_text and attempt.word_count is None:
                stage_transcribe(attempt, path)
        if not hasattr(attempt, "evaluation"):
            stage_evaluate(attempt)
        stage_schedule(attempt)
    except StageError as exc:
        _fail(attempt, exc.stage, exc.message)
        return attempt
    attempt.status = AttemptStatus.COMPLETED
    attempt.failure_stage = ""
    attempt.error_message = ""
    attempt.completed_at = timezone.now()
    attempt.save(
        update_fields=["status", "failure_stage", "error_message", "completed_at", "updated_at"]
    )
    if attempt.session_id:
        refresh_status(attempt.session)
    return attempt


def stage_probe(attempt: Attempt, path: Path) -> None:
    _set_status(attempt, AttemptStatus.PROBING)
    try:
        probe = get_prober().probe(path)
    except AudioProbeError as exc:
        raise StageError("probing", str(exc)) from exc
    duration = probe.duration_seconds
    if duration < settings.ECHO_AUDIO_MIN_SECONDS:
        raise StageError(
            "probing",
            f"Recording too short ({duration:.1f} s); "
            f"minimum is {settings.ECHO_AUDIO_MIN_SECONDS:.0f} s.",
        )
    if duration > settings.ECHO_AUDIO_MAX_SECONDS:
        raise StageError(
            "probing",
            f"Recording too long ({duration:.0f} s); "
            f"maximum is {settings.ECHO_AUDIO_MAX_SECONDS:.0f} s.",
        )
    attempt.audio_duration_seconds = Decimal(str(round(duration, 2)))
    attempt.save(update_fields=["audio_duration_seconds", "updated_at"])


def stage_transcribe(attempt: Attempt, path: Path) -> None:
    _set_status(attempt, AttemptStatus.TRANSCRIBING)
    try:
        result = ai_services.transcribe_audio(
            user=attempt.user,
            path=path,
            audio_seconds=float(attempt.audio_duration_seconds or 0),
            language=attempt.card.language,
            related=attempt,
        )
    except TranscriptionError as exc:
        raise StageError("transcribing", str(exc)) from exc
    words = len(result.text.split())
    duration = float(attempt.audio_duration_seconds or 0) or (result.duration_seconds or 0)
    wpm = Decimal(str(round(words / (duration / 60), 1))) if duration > 0 else None
    attempt.transcript_text = result.text
    attempt.transcript_segments = result.segments
    attempt.word_count = words
    attempt.words_per_minute = wpm
    attempt.transcription_model = result.model
    attempt.save(
        update_fields=[
            "transcript_text",
            "transcript_segments",
            "word_count",
            "words_per_minute",
            "transcription_model",
            "updated_at",
        ]
    )


def stage_evaluate(attempt: Attempt) -> None:
    _set_status(attempt, AttemptStatus.EVALUATING)
    user = attempt.user
    word_count = attempt.word_count or 0
    if word_count < settings.ECHO_MIN_WORDS_FOR_EVALUATION:
        note = INSUFFICIENT_SPEECH_FEEDBACK.get(
            user.feedback_language, INSUFFICIENT_SPEECH_FEEDBACK["en"]
        )
        composite = sm2.composite_score(1, 1, 1)
        Evaluation.objects.create(
            user=user,
            attempt=attempt,
            structure_score=1,
            grammar_score=1,
            fluency_score=1,
            structure_feedback=note,
            grammar_feedback=note,
            fluency_feedback=note,
            grammar_issues=[],
            fluency_markers={"fillers": 0, "false_starts": 0, "repetitions": 0},
            composite_score=composite,
            sm2_quality=sm2.quality_from_composite(composite, 1),
            model="none",
            prompt_version=settings.ECHO_PROMPT_VERSION,
            raw_response={"reason": "insufficient_speech", "word_count": word_count},
        )
        attempt.insufficient_speech = True
        attempt.save(update_fields=["insufficient_speech", "updated_at"])
        attempt.evaluation = Evaluation.objects.get(attempt=attempt)
        return

    try:
        result = ai_services.evaluate_transcript(
            user=user,
            card=attempt.card,
            transcript_text=attempt.transcript_text,
            duration_seconds=float(attempt.audio_duration_seconds or 0),
            word_count=word_count,
            words_per_minute=float(attempt.words_per_minute or 0),
            related=attempt,
        )
    except AIError as exc:
        raise StageError("evaluating", str(exc)) from exc

    out = result.parsed
    composite = sm2.composite_score(out.structure.score, out.grammar.score, out.fluency.score)
    evaluation = Evaluation.objects.create(
        user=user,
        attempt=attempt,
        structure_score=out.structure.score,
        grammar_score=out.grammar.score,
        fluency_score=out.fluency.score,
        structure_feedback=out.structure.feedback,
        grammar_feedback=out.grammar.feedback,
        fluency_feedback=out.fluency.feedback,
        grammar_issues=[issue.model_dump() for issue in out.grammar.issues[:5]],
        fluency_markers=out.fluency.markers.model_dump(),
        composite_score=composite,
        sm2_quality=sm2.quality_from_composite(composite, out.structure.score),
        model=result.model,
        prompt_version=settings.ECHO_PROMPT_VERSION,
        raw_response=result.raw,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
    )
    attempt.evaluation = evaluation


def stage_schedule(attempt: Attempt) -> None:
    _set_status(attempt, AttemptStatus.SCHEDULING)
    evaluation = attempt.evaluation
    already_counted_today = (
        Attempt.objects.filter(
            card=attempt.card, attempted_on=attempt.attempted_on, counts_for_scheduling=True
        )
        .exclude(pk=attempt.pk)
        .exists()
    )
    counts = not attempt.insufficient_speech and not already_counted_today
    if not counts:
        attempt.counts_for_scheduling = False
        attempt.save(update_fields=["counts_for_scheduling", "updated_at"])
        return
    try:
        with transaction.atomic():
            apply_review(
                card=attempt.card,
                attempt=attempt,
                composite=evaluation.composite_score,
                quality=evaluation.sm2_quality,
                reviewed_on=attempt.attempted_on,
            )
            apply_level_result(
                user=attempt.user,
                card=attempt.card,
                attempt=attempt,
                composite=evaluation.composite_score,
                logged_on=attempt.attempted_on,
            )
            attempt.counts_for_scheduling = True
            attempt.save(update_fields=["counts_for_scheduling", "updated_at"])
    except LanguageProfile.DoesNotExist as exc:
        raise StageError(
            "scheduling", f"No language profile for {attempt.card.language!r}."
        ) from exc
