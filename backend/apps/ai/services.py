"""AI use cases: generate questions, evaluate a transcript, improve an answer, transcribe.

Every call is logged to `AIRequestLog` with an estimated cost, inside the caller's owner context.
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal

from django.conf import settings

from apps.ai import pricing, prompts
from apps.ai.clients import get_llm, get_transcriber
from apps.ai.clients.base import LLMResult, TranscriptionResult
from apps.ai.exceptions import AIError, TranscriptionError
from apps.ai.models import AIRequestKind, AIRequestLog, AIRequestStatus
from apps.ai.schemas import EvaluationOutput, GenerationOutput, ImprovedAnswerOutput

log = logging.getLogger("echo.ai")


def _log_llm(
    user,
    kind: str,
    result: LLMResult | None,
    *,
    model: str,
    error: str = "",
    latency_ms: int = 0,
    related=None,
) -> AIRequestLog:
    return AIRequestLog.objects.create(
        user=user,
        kind=kind,
        provider=get_llm().provider,
        model=result.model if result else model,
        input_tokens=result.input_tokens if result else 0,
        output_tokens=result.output_tokens if result else 0,
        cache_read_input_tokens=result.cache_read_input_tokens if result else 0,
        cache_creation_input_tokens=result.cache_creation_input_tokens if result else 0,
        estimated_cost_usd=(
            pricing.token_cost(
                result.model,
                result.input_tokens,
                result.output_tokens,
                result.cache_read_input_tokens,
                result.cache_creation_input_tokens,
            )
            if result
            else Decimal(0)
        ),
        latency_ms=result.latency_ms if result else latency_ms,
        status=AIRequestStatus.OK if result else AIRequestStatus.ERROR,
        error=error[:2000],
        related_object_type=type(related).__name__ if related is not None else "",
        related_object_id=getattr(related, "pk", None),
    )


def _call(
    user,
    kind: str,
    *,
    model: str,
    system: str,
    user_message: str,
    output_format,
    effort: str,
    related=None,
    timeout: float | None = None,
    max_tokens: int = 8000,
):
    started = time.monotonic()
    try:
        result = get_llm().parse(
            model=model,
            system=system,
            user=user_message,
            output_format=output_format,
            effort=effort,
            max_tokens=max_tokens,
            timeout=timeout,
        )
    except AIError as exc:
        _log_llm(
            user,
            kind,
            None,
            model=model,
            error=str(exc),
            latency_ms=int((time.monotonic() - started) * 1000),
            related=related,
        )
        log.warning("ai.%s failed for user=%s: %s", kind, user.pk, exc)
        raise
    _log_llm(user, kind, result, model=model, related=related)
    return result


# --- Generation --------------------------------------------------------------------------------


def generate_questions(
    *, user, slots, categories, recent_questions, related=None
) -> LLMResult[GenerationOutput]:
    return _call(
        user,
        AIRequestKind.GENERATE_QUESTIONS,
        model=settings.ECHO_GENERATION_MODEL,
        system=prompts.generation_system(),
        user_message=prompts.generation_user(slots, categories, recent_questions),
        output_format=GenerationOutput,
        effort=settings.ECHO_GENERATION_EFFORT,
        related=related,
    )


# --- Evaluation --------------------------------------------------------------------------------


def evaluate_transcript(
    *,
    user,
    card,
    transcript_text: str,
    duration_seconds: float,
    word_count: int,
    words_per_minute: float,
    related=None,
) -> LLMResult[EvaluationOutput]:
    return _call(
        user,
        AIRequestKind.EVALUATE,
        model=settings.ECHO_EVALUATION_MODEL,
        system=prompts.evaluation_system(card.cefr_level, user.feedback_language),
        user_message=prompts.evaluation_user(
            category_name=card.category.name,
            question_level=card.cefr_level,
            scenario=card.scenario,
            question_text=card.question_text,
            key_points=list(card.key_points or []),
            transcript_text=transcript_text,
            duration_seconds=duration_seconds,
            word_count=word_count,
            words_per_minute=words_per_minute,
        ),
        output_format=EvaluationOutput,
        effort=settings.ECHO_EVALUATION_EFFORT,
        related=related,
    )


# --- Improved answer (on demand) -------------------------------------------------------------


def improve_answer(
    *, user, card, transcript_text: str, issues: list[dict], related=None
) -> LLMResult[ImprovedAnswerOutput]:
    return _call(
        user,
        AIRequestKind.IMPROVE_ANSWER,
        model=settings.ECHO_IMPROVED_ANSWER_MODEL,
        system=prompts.improved_answer_system(card.cefr_level, user.feedback_language),
        user_message=prompts.improved_answer_user(
            question_text=card.question_text,
            scenario=card.scenario,
            transcript_text=transcript_text,
            issues=issues,
        ),
        output_format=ImprovedAnswerOutput,
        effort=settings.ECHO_IMPROVED_ANSWER_EFFORT,
        related=related,
        timeout=settings.ECHO_IMPROVED_ANSWER_TIMEOUT_SECONDS,
        max_tokens=4000,
    )


# --- Transcription -----------------------------------------------------------------------------


def transcribe_audio(
    *, user, path, audio_seconds: float | None, related=None
) -> TranscriptionResult:
    transcriber = get_transcriber()
    model = settings.ECHO_TRANSCRIPTION_MODEL
    started = time.monotonic()
    try:
        result = transcriber.transcribe(path, model=model)
    except TranscriptionError as exc:
        AIRequestLog.objects.create(
            user=user,
            kind=AIRequestKind.TRANSCRIBE,
            provider=transcriber.provider,
            model=model,
            audio_seconds=Decimal(str(audio_seconds)) if audio_seconds else None,
            latency_ms=int((time.monotonic() - started) * 1000),
            status=AIRequestStatus.ERROR,
            error=str(exc)[:2000],
            related_object_type=type(related).__name__ if related is not None else "",
            related_object_id=getattr(related, "pk", None),
        )
        raise
    seconds = audio_seconds or result.duration_seconds or 0
    AIRequestLog.objects.create(
        user=user,
        kind=AIRequestKind.TRANSCRIBE,
        provider=transcriber.provider,
        model=result.model,
        audio_seconds=Decimal(str(round(seconds, 2))),
        estimated_cost_usd=pricing.audio_cost(result.model, seconds),
        latency_ms=result.latency_ms,
        status=AIRequestStatus.OK,
        related_object_type=type(related).__name__ if related is not None else "",
        related_object_id=getattr(related, "pk", None),
    )
    return result
