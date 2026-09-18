"""Session lifecycle: projection, creation with carry-over, slot generation, status refresh."""

from __future__ import annotations

import datetime as dt
import logging
import re
import unicodedata
from dataclasses import asdict, dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.ai import services as ai_services
from apps.ai.exceptions import AIError
from apps.cards.models import Card, CardSource, CardStatus, Category
from apps.core.exceptions import ConflictError
from apps.leveling.elo import band_for_rating, rating_for_level
from apps.leveling.probes import plan_slots, probe_count
from apps.practice import queue
from apps.practice.models import (
    Attempt,
    AttemptStatus,
    DailySession,
    NewCardOrigin,
    SessionNewCard,
    SessionStatus,
)
from apps.scheduling.models import Maturity, SchedulerState

log = logging.getLogger("echo.practice")


@dataclass
class Projection:
    carried_over: int
    to_generate: int
    due_today: int
    overdue: int
    probes: int
    base_level: str

    @property
    def total(self) -> int:
        return self.carried_over + self.to_generate + self.due_today

    def as_dict(self) -> dict:
        return {**asdict(self), "total": self.total}


def carried_over_cards(user):
    """Active `new` cards never answered (with a counted attempt) — they come back first."""
    return (
        Card.objects.filter(status=CardStatus.ACTIVE, scheduler__maturity=Maturity.NEW)
        .select_related("scheduler")
        .order_by("created_at")
    )


def project_session(
    user, *, new_cards_target: int, session_date: dt.date | None = None, categories=None
) -> Projection:
    session_date = session_date or user.local_today()
    carried = min(new_cards_target, carried_over_cards(user).count())
    to_generate = max(0, new_cards_target - carried)
    if not categories:
        to_generate = 0
    due_qs = queue.due_cards(user, session_date)
    due_today = due_qs.count()
    overdue = due_qs.filter(scheduler__due_date__lt=session_date).count()
    return Projection(
        carried_over=carried,
        to_generate=to_generate,
        due_today=due_today,
        overdue=overdue,
        probes=probe_count(to_generate),
        base_level=band_for_rating(user.level_rating),
    )


def resolve_categories(user, category_ids) -> list[Category]:
    ids = list(dict.fromkeys(str(i) for i in category_ids))
    found = {str(c.id): c for c in Category.objects.visible_to(user).active().filter(pk__in=ids)}
    missing = [i for i in ids if i not in found]
    if missing:
        from rest_framework.exceptions import ValidationError

        raise ValidationError(
            {"category_ids": [f"Unknown or inactive category: {missing[0]}"]},
            code="unknown_category",
        )
    return [found[i] for i in ids]


def create_session(user, *, category_ids, new_cards_target: int) -> DailySession:
    session_date = user.local_today()
    existing = DailySession.objects.filter(session_date=session_date).first()
    if existing is not None:
        raise ConflictError(
            "A session already exists for today.",
            code="session_exists",
            extra={"session_id": str(existing.id)},
        )
    categories = resolve_categories(user, category_ids)
    if new_cards_target > 0 and not categories:
        from rest_framework.exceptions import ValidationError

        raise ValidationError(
            {"category_ids": ["Choose at least one category to generate new cards."]},
            code="no_categories",
        )

    from apps.practice.tasks import generate_session_cards

    with transaction.atomic():
        session = DailySession.objects.create(
            user=user,
            session_date=session_date,
            new_cards_target=new_cards_target,
            rating_at_start=user.level_rating,
            status=SessionStatus.GENERATING,
        )
        session.categories.set(categories)
        carried = list(carried_over_cards(user)[:new_cards_target])
        SessionNewCard.objects.bulk_create(
            [
                SessionNewCard(
                    user=user,
                    session=session,
                    card=card,
                    position=position,
                    origin=NewCardOrigin.CARRIED_OVER,
                )
                for position, card in enumerate(carried, start=1)
            ]
        )
        to_generate = max(0, new_cards_target - len(carried))
        if to_generate > 0 and categories:
            from apps.core.tasks import enqueue

            enqueue(generate_session_cards, session_id=str(session.id), user_id=str(user.id))
        else:
            session.status = SessionStatus.READY
            session.save(update_fields=["status", "updated_at"])
    session.refresh_from_db()
    return session


# --- Generation -------------------------------------------------------------------------------

_NORMALISE_RE = re.compile(r"[^a-z0-9 ]+")


def normalise_question(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(_NORMALISE_RE.sub(" ", text.lower()).split())


def run_generation(session: DailySession) -> list[Card]:
    """Generate the missing new cards for a session. Runs inside the owner context (worker)."""
    user = session.user
    categories = list(session.categories.all().order_by("sort_order", "name"))
    carried = SessionNewCard.objects.filter(session=session).count()
    to_generate = max(0, session.new_cards_target - carried)
    if to_generate == 0 or not categories:
        session.status = SessionStatus.READY
        session.save(update_fields=["status", "updated_at"])
        return []

    base_level = band_for_rating(session.rating_at_start)
    slots = plan_slots(to_generate, categories, base_level)
    recent = list(
        Card.objects.filter(category__in=categories)
        .order_by("-created_at")
        .values_list("category__slug", "question_text")[: settings.ECHO_GENERATION_RECENT_QUESTIONS]
    )
    try:
        result = ai_services.generate_questions(
            user=user, slots=slots, categories=categories, recent_questions=recent, related=session
        )
    except AIError as exc:
        session.status = SessionStatus.FAILED
        session.generation_error = str(exc)[:1000]
        session.save(update_fields=["status", "generation_error", "updated_at"])
        return []

    by_slot = {q.slot: q for q in result.parsed.questions}
    existing = {normalise_question(t) for t in Card.objects.values_list("question_text", flat=True)}
    created: list[Card] = []
    with transaction.atomic():
        position = carried
        for slot in slots:
            question = by_slot.get(slot.number)
            if question is None:
                log.warning(
                    "generation: slot %s missing in response (session=%s)", slot.number, session.id
                )
                continue
            key = normalise_question(question.question)
            if not key or key in existing:
                log.info("generation: duplicate question skipped (session=%s)", session.id)
                continue
            existing.add(key)
            position += 1
            card = Card.objects.create(
                user=user,
                category=slot.category,  # backend prevails over the model's echo
                question_text=question.question.strip(),
                scenario=(question.scenario or "").strip() or None,
                key_points=[p.strip() for p in question.key_points if p.strip()][:4],
                cefr_level=slot.level,
                difficulty_rating=rating_for_level(slot.level, question.difficulty_within_level),
                probe=slot.probe,
                status=CardStatus.ACTIVE,
                source=CardSource.GENERATED,
                created_in_session=session,
                generation_model=result.model,
                prompt_version=settings.ECHO_PROMPT_VERSION,
            )
            SchedulerState.objects.create(user=user, card=card)
            SessionNewCard.objects.create(
                user=user,
                session=session,
                card=card,
                position=position,
                origin=NewCardOrigin.GENERATED,
            )
            created.append(card)
        if not created:
            session.status = SessionStatus.FAILED
            session.generation_error = "The generator returned no usable questions."
        else:
            session.status = SessionStatus.READY
            session.generation_error = ""
        session.save(update_fields=["status", "generation_error", "updated_at"])
    return created


def retry_generation(session: DailySession) -> DailySession:
    if session.status != SessionStatus.FAILED:
        raise ConflictError("Only failed sessions can be retried.", code="not_failed")
    from apps.core.tasks import enqueue
    from apps.practice.tasks import generate_session_cards

    session.status = SessionStatus.GENERATING
    session.generation_error = ""
    session.save(update_fields=["status", "generation_error", "updated_at"])
    enqueue(generate_session_cards, session_id=str(session.id), user_id=str(session.user_id))
    session.refresh_from_db()
    return session


# --- Status ------------------------------------------------------------------------------------


def refresh_status(session: DailySession) -> DailySession:
    if session.status not in {SessionStatus.READY, SessionStatus.IN_PROGRESS}:
        return session
    if queue.progress(session)["remaining"] == 0:
        session.status = SessionStatus.COMPLETED
        session.completed_at = session.completed_at or timezone.now()
        session.save(update_fields=["status", "completed_at", "updated_at"])
    elif session.status == SessionStatus.READY and Attempt.objects.filter(session=session).exists():
        session.status = SessionStatus.IN_PROGRESS
        session.save(update_fields=["status", "updated_at"])
    return session


def complete_session(session: DailySession) -> DailySession:
    if session.status in {SessionStatus.READY, SessionStatus.IN_PROGRESS}:
        session.status = SessionStatus.COMPLETED
        session.completed_at = timezone.now()
        session.save(update_fields=["status", "completed_at", "updated_at"])
    return session


def card_history(card: Card):
    return (
        Attempt.objects.filter(card=card)
        .select_related("evaluation", "review", "level_change", "session")
        .order_by("-attempt_number")
    )


def today_session(user) -> DailySession | None:
    return DailySession.objects.filter(session_date=user.local_today()).first()


def latest_completed_attempt(card: Card) -> Attempt | None:
    return (
        Attempt.objects.filter(card=card, status=AttemptStatus.COMPLETED)
        .order_by("-attempt_number")
        .first()
    )
