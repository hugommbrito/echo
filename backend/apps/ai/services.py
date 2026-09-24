"""AI use cases: generate questions, evaluate a transcript, improve an answer, transcribe, speak.

Every call is logged to `AIRequestLog` with an estimated cost and the key that paid for it (the
user's own or the global one — see `apps.ai.routing`), inside the caller's owner context.
"""

from __future__ import annotations

import logging
import re
import tempfile
import time
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile

from apps.ai import pricing, prompts
from apps.ai.clients import get_llm, get_prober, get_transcriber, get_tts
from apps.ai.clients.base import LLMResult, TranscriptionResult
from apps.ai.exceptions import AIConfigurationError, AIError, AudioProbeError
from apps.ai.models import AIRequestKind, AIRequestLog, AIRequestStatus, KeySource
from apps.ai.schemas import EvaluationOutput, GenerationOutput, ImprovedAnswerOutput
from apps.core.languages import LanguageSpec, get_language

log = logging.getLogger("echo.ai")

_SECRET_RE = re.compile(r"sk-[A-Za-z0-9_\-]{6,}")


def redact(message: str | None) -> str:
    """Strip anything that looks like a provider key before persisting or logging an error."""
    return _SECRET_RE.sub("sk-…", message or "")


def model_for(provider: str, task: str) -> str:
    """Model id for a text task on a provider (the fake provider reuses the Anthropic table)."""
    table = settings.ECHO_MODELS.get(provider) or settings.ECHO_MODELS["anthropic"]
    try:
        return table[task]
    except KeyError:
        raise AIConfigurationError(f"No model configured for task {task!r}.")


def _related(related) -> dict:
    return {
        "related_object_type": type(related).__name__ if related is not None else "",
        "related_object_id": getattr(related, "pk", None),
    }


def _log_llm(
    user,
    kind: str,
    result: LLMResult | None,
    *,
    provider: str,
    key_source: str,
    model: str,
    error: str = "",
    latency_ms: int = 0,
    related=None,
    language: str = "",
) -> AIRequestLog:
    return AIRequestLog.objects.create(
        user=user,
        kind=kind,
        language=language,
        provider=provider,
        key_source=key_source,
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
        error=redact(error)[:2000],
        **_related(related),
    )


def _log_audio(
    user,
    kind: str,
    *,
    provider: str,
    key_source: str,
    model: str,
    language: str,
    seconds: float | None,
    latency_ms: int,
    error: str = "",
    cost: Decimal | None = None,
    related=None,
) -> AIRequestLog:
    return AIRequestLog.objects.create(
        user=user,
        kind=kind,
        language=language,
        provider=provider,
        key_source=key_source,
        model=model,
        audio_seconds=Decimal(str(round(seconds, 2))) if seconds else None,
        estimated_cost_usd=cost if cost is not None else Decimal(0),
        latency_ms=latency_ms,
        status=AIRequestStatus.ERROR if error else AIRequestStatus.OK,
        error=redact(error)[:2000],
        **_related(related),
    )


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _call(
    user,
    kind: str,
    *,
    task: str,
    system: str,
    user_message: str,
    output_format,
    effort: str,
    related=None,
    timeout: float | None = None,
    max_tokens: int = 8000,
    language: str = "",
):
    started = time.monotonic()
    try:
        client, key = get_llm(user)
    except AIConfigurationError as exc:
        _log_llm(
            user,
            kind,
            None,
            provider="none",
            key_source=KeySource.GLOBAL,
            model="",
            error=str(exc),
            related=related,
            language=language,
        )
        log.warning("ai.%s not configured for user=%s: %s", kind, user.pk, exc)
        raise
    model = model_for(client.provider, task)
    try:
        result = client.parse(
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
            provider=client.provider,
            key_source=key.source,
            model=model,
            error=str(exc),
            latency_ms=_elapsed_ms(started),
            related=related,
            language=language,
        )
        log.warning("ai.%s failed for user=%s: %s", kind, user.pk, redact(str(exc)))
        raise
    _log_llm(
        user,
        kind,
        result,
        provider=client.provider,
        key_source=key.source,
        model=model,
        related=related,
        language=language,
    )
    return result


# --- Generation --------------------------------------------------------------------------------


def generate_questions(
    *, user, language: LanguageSpec, slots, categories, recent_questions, related=None
) -> LLMResult[GenerationOutput]:
    return _call(
        user,
        AIRequestKind.GENERATE_QUESTIONS,
        task="generation",
        system=prompts.generation_system(language),
        user_message=prompts.generation_user(slots, categories, recent_questions),
        output_format=GenerationOutput,
        effort=settings.ECHO_GENERATION_EFFORT,
        related=related,
        language=language.code,
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
    thinking_seconds: float | None = None,
    thinking_baseline_seconds: float | None = None,
    related=None,
) -> LLMResult[EvaluationOutput]:
    language = get_language(card.language)
    return _call(
        user,
        AIRequestKind.EVALUATE,
        task="evaluation",
        system=prompts.evaluation_system(language, card.cefr_level, user.feedback_language),
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
            thinking_seconds=thinking_seconds,
            thinking_baseline_seconds=thinking_baseline_seconds,
        ),
        output_format=EvaluationOutput,
        effort=settings.ECHO_EVALUATION_EFFORT,
        related=related,
        language=language.code,
    )


# --- Improved answer (on demand) -------------------------------------------------------------


def improve_answer(
    *, user, card, transcript_text: str, issues: list[dict], related=None
) -> LLMResult[ImprovedAnswerOutput]:
    language = get_language(card.language)
    return _call(
        user,
        AIRequestKind.IMPROVE_ANSWER,
        task="improved_answer",
        system=prompts.improved_answer_system(language, card.cefr_level, user.feedback_language),
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
        language=language.code,
    )


# --- Transcription -----------------------------------------------------------------------------


def transcribe_audio(
    *, user, path, audio_seconds: float | None, language: str, related=None
) -> TranscriptionResult:
    spec = get_language(language)
    model = settings.ECHO_TRANSCRIPTION_MODEL
    started = time.monotonic()
    try:
        transcriber, key = get_transcriber(user)
    except AIConfigurationError as exc:
        _log_audio(
            user,
            AIRequestKind.TRANSCRIBE,
            provider="none",
            key_source=KeySource.GLOBAL,
            model=model,
            language=spec.code,
            seconds=audio_seconds,
            latency_ms=0,
            error=str(exc),
            related=related,
        )
        raise
    try:
        result = transcriber.transcribe(
            path, model=model, language=spec.whisper_code, prompt=prompts.whisper_prompt(spec)
        )
    except AIError as exc:
        _log_audio(
            user,
            AIRequestKind.TRANSCRIBE,
            provider=transcriber.provider,
            key_source=key.source,
            model=model,
            language=spec.code,
            seconds=audio_seconds,
            latency_ms=_elapsed_ms(started),
            error=str(exc),
            related=related,
        )
        log.warning("ai.transcribe failed for user=%s: %s", user.pk, redact(str(exc)))
        raise
    seconds = audio_seconds or result.duration_seconds or 0
    _log_audio(
        user,
        AIRequestKind.TRANSCRIBE,
        provider=transcriber.provider,
        key_source=key.source,
        model=result.model,
        language=spec.code,
        seconds=seconds,
        latency_ms=result.latency_ms,
        cost=pricing.audio_cost(result.model, seconds),
        related=related,
    )
    return result


# --- Text-to-speech (spoken question) ---------------------------------------------------------


def _measure_audio_seconds(audio: bytes, response_format: str) -> float | None:
    """Real duration via ffprobe; None (not an error) when the file cannot be probed."""
    suffix = f".{response_format}" if response_format else ""
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        tmp.write(audio)
        tmp.flush()
        try:
            return get_prober().probe(Path(tmp.name)).duration_seconds
        except AudioProbeError as exc:
            log.warning("ai.tts: could not measure the generated audio: %s", exc)
            return None


def synthesize_question_audio(*, card, force: bool = False, timeout: float | None = None) -> bool:
    """Generate and store the spoken question of a card.

    Idempotent: returns False when the card already has audio (unless `force`). Failures are
    logged to `AIRequestLog` and re-raised as `AIError`; the card stays fully usable without audio.
    """
    if card.question_audio and not force:
        return False
    user = card.user
    spec = get_language(card.language)
    model = settings.ECHO_TTS_MODEL
    voices = settings.ECHO_TTS_VOICES
    voice = voices.get(card.language) or next(iter(voices.values()))
    instructions = settings.ECHO_TTS_INSTRUCTIONS.get(card.language) or None
    started = time.monotonic()
    try:
        tts, key = get_tts(user)
    except AIConfigurationError as exc:
        _log_audio(
            user,
            AIRequestKind.TTS,
            provider="none",
            key_source=KeySource.GLOBAL,
            model=model,
            language=spec.code,
            seconds=None,
            latency_ms=0,
            error=str(exc),
            related=card,
        )
        raise
    try:
        result = tts.synthesize(
            card.question_text,
            model=model,
            voice=voice,
            instructions=instructions,
            response_format=settings.ECHO_TTS_FORMAT,
            timeout=timeout,
        )
    except AIError as exc:
        _log_audio(
            user,
            AIRequestKind.TTS,
            provider=tts.provider,
            key_source=key.source,
            model=model,
            language=spec.code,
            seconds=None,
            latency_ms=_elapsed_ms(started),
            error=str(exc),
            related=card,
        )
        log.warning("ai.tts failed for card=%s: %s", card.pk, redact(str(exc)))
        raise

    seconds = _measure_audio_seconds(result.audio, result.response_format)
    # The worker and the lazy endpoint may race on a fresh card: the first file to land wins.
    current = (
        type(card).all_users.filter(pk=card.pk).values_list("question_audio", flat=True).first()
    )
    if current and not force:
        return False
    if force and card.question_audio:
        card.question_audio.delete(save=False)
    card.question_audio.save(
        f"{card.id}.{result.response_format}", ContentFile(result.audio), save=False
    )
    card.question_audio_seconds = Decimal(str(round(seconds, 2))) if seconds else None
    card.question_audio_model = result.model
    card.question_audio_voice = result.voice
    card.save(
        update_fields=[
            "question_audio",
            "question_audio_seconds",
            "question_audio_model",
            "question_audio_voice",
            "updated_at",
        ]
    )
    _log_audio(
        user,
        AIRequestKind.TTS,
        provider=tts.provider,
        key_source=key.source,
        model=result.model,
        language=spec.code,
        seconds=seconds,
        latency_ms=result.latency_ms,
        cost=pricing.tts_cost(result.model, seconds),
        related=card,
    )
    return True
