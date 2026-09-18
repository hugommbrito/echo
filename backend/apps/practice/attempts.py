"""Attempt creation (upload) and retry."""

from __future__ import annotations

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.cards.models import Card, CardStatus
from apps.core.exceptions import ConflictError
from apps.core.storage import extension_for
from apps.core.tasks import enqueue
from apps.practice.models import Attempt, AttemptStatus, DailySession
from apps.practice.tasks import process_attempt

ALLOWED_AUDIO_PREFIXES = ("audio/", "video/webm", "video/mp4", "application/octet-stream")


def create_attempt(
    user, *, card_id, session_id, audio, mime_type: str | None, client_duration
) -> Attempt:
    if audio is None:
        raise ValidationError({"audio": ["An audio file is required."]}, code="audio_required")
    if audio.size == 0:
        raise ValidationError({"audio": ["The audio file is empty."]}, code="audio_empty")
    if audio.size > settings.ECHO_AUDIO_MAX_UPLOAD_BYTES:
        raise ValidationError({"audio": ["The audio file exceeds 25 MB."]}, code="audio_too_large")
    mime = (
        (mime_type or getattr(audio, "content_type", "") or "application/octet-stream")
        .split(";")[0]
        .strip()
        .lower()
    )
    if not mime.startswith(ALLOWED_AUDIO_PREFIXES):
        raise ValidationError({"audio": [f"Unsupported audio type: {mime}"]}, code="audio_type")
    if client_duration is not None and client_duration > settings.ECHO_AUDIO_MAX_SECONDS + 5:
        raise ValidationError(
            {"duration_seconds": ["Recording longer than 5 minutes."]}, code="too_long"
        )

    with transaction.atomic():
        try:
            card = Card.objects.select_for_update().get(pk=card_id)
        except (Card.DoesNotExist, ValueError, TypeError):
            raise ValidationError({"card_id": ["Unknown card."]}, code="unknown_card")
        if card.status != CardStatus.ACTIVE:
            raise ConflictError("This card is suspended.", code="card_suspended")
        session = None
        if session_id:
            session = DailySession.objects.filter(pk=session_id).first()
            if session is None:
                raise ValidationError({"session_id": ["Unknown session."]}, code="unknown_session")
        attempt_number = Attempt.objects.filter(card=card).count() + 1
        attempt = Attempt(
            user=user,
            card=card,
            session=session,
            attempt_number=attempt_number,
            attempted_on=user.local_today(),
            audio_mime=mime,
            audio_size_bytes=audio.size,
            client_duration_seconds=client_duration,
            status=AttemptStatus.UPLOADED,
        )
        filename = f"{attempt.id}.{extension_for(mime, getattr(audio, 'name', None))}"
        attempt.audio_file.save(filename, audio, save=False)
        attempt.save()
        enqueue(process_attempt, attempt_id=str(attempt.id), user_id=str(user.id))
    attempt.refresh_from_db()
    return attempt


def retry_attempt(attempt: Attempt) -> Attempt:
    if attempt.status != AttemptStatus.FAILED:
        raise ConflictError("Only failed attempts can be retried.", code="not_failed")
    attempt.status = AttemptStatus.UPLOADED
    attempt.save(update_fields=["status", "updated_at"])
    enqueue(process_attempt, attempt_id=str(attempt.id), user_id=str(attempt.user_id))
    attempt.refresh_from_db()
    return attempt
