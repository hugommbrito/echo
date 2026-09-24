"""Session lifecycle: projection, creation with carry-over, slot generation, status refresh.

One daily session mixes the learner's active languages: each language has its own
`SessionLanguagePlan` (target, rating snapshot, generation state) and its own Sonnet call.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.accounts import services as account_services
from apps.ai import services as ai_services
from apps.ai.exceptions import AIError
from apps.cards.models import Card, CardSource, CardStatus, Category
from apps.cards.tasks import synthesize_question_audio
from apps.core.exceptions import ConflictError
from apps.core.languages import get_language, is_known_language
from apps.core.tasks import enqueue
from apps.leveling.elo import band_for_rating, rating_for_level
from apps.leveling.probes import plan_slots, probe_count
from apps.practice import queue
from apps.practice.models import (
    Attempt,
    AttemptStatus,
    DailySession,
    NewCardOrigin,
    PlanStatus,
    SessionLanguagePlan,
    SessionNewCard,
    SessionStatus,
)
from apps.scheduling.models import Maturity, SchedulerState

log = logging.getLogger("echo.practice")


# --- Projection ------------------------------------------------------------------------------


@dataclass
class LanguageProjection:
    language: str
    base_level: str
    carried_over: int
    available_carry_over: int
    to_generate: int
    probes: int
    due_today: int
    overdue: int

    @property
    def total(self) -> int:
        return self.carried_over + self.to_generate + self.due_today

    def as_dict(self) -> dict:
        return {
            "language": self.language,
            "base_level": self.base_level,
            "carried_over": self.carried_over,
            "available_carry_over": self.available_carry_over,
            "to_generate": self.to_generate,
            "probes": self.probes,
            "due_today": self.due_today,
            "overdue": self.overdue,
            "total": self.total,
        }


@dataclass
class SessionProjection:
    languages: list[LanguageProjection] = field(default_factory=list)

    def _sum(self, name: str) -> int:
        return sum(getattr(lp, name) for lp in self.languages)

    def as_dict(self) -> dict:
        return {
            "languages": [lp.as_dict() for lp in self.languages],
            "carried_over": self._sum("carried_over"),
            "to_generate": self._sum("to_generate"),
            "due_today": self._sum("due_today"),
            "overdue": self._sum("overdue"),
            "probes": self._sum("probes"),
            "total": self._sum("total"),
        }


def carried_over_cards(user, language: str):
    """Active `new` cards of one language never answered (with a counted attempt)."""
    return (
        Card.objects.filter(
            status=CardStatus.ACTIVE, scheduler__maturity=Maturity.NEW, language=language
        )
        .select_related("scheduler")
        .order_by("created_at")
    )


def default_targets(user) -> dict[str, int]:
    return {
        profile.language: profile.default_new_cards_per_day
        for profile in account_services.active_profiles(user)
    }


def resolve_targets(user, raw: Mapping[str, int] | None) -> dict[str, int]:
    """Per-language targets restricted to the learner's *active* languages (absent = 0)."""
    from rest_framework.exceptions import ValidationError

    active = account_services.active_language_codes(user)
    if not active:
        raise ValidationError(
            {"new_cards_targets": ["Activate at least one language first."]},
            code="no_active_languages",
        )
    targets = {code: 0 for code in active}
    for code, value in (raw or {}).items():
        if not is_known_language(code):
            raise ValidationError(
                {"new_cards_targets": [f"Unknown language: {code}"]}, code="unknown_language"
            )
        if code not in targets:
            raise ValidationError(
                {"new_cards_targets": [f"Language '{code}' is not active."]},
                code="language_not_active",
            )
        try:
            count = int(value)
        except (TypeError, ValueError):
            raise ValidationError({"new_cards_targets": ["Targets must be integers."]})
        if not 0 <= count <= settings.ECHO_MAX_NEW_CARDS_PER_DAY:
            raise ValidationError(
                {
                    "new_cards_targets": [
                        f"Targets must be between 0 and {settings.ECHO_MAX_NEW_CARDS_PER_DAY}."
                    ]
                },
                code="out_of_range",
            )
        targets[code] = count
    return targets


def parse_targets_param(raw: str | None) -> dict[str, int] | None:
    """`en:3,fr:2` -> {"en": 3, "fr": 2}; None when the parameter is absent."""
    from rest_framework.exceptions import ValidationError

    if raw is None or raw == "":
        return None
    result: dict[str, int] = {}
    for part in raw.split(","):
        code, sep, count = part.strip().partition(":")
        if not sep or not code:
            raise ValidationError(
                {"targets": ["Use lang:count pairs, e.g. en:3,fr:2"]}, code="invalid_targets"
            )
        try:
            result[code] = int(count)
        except ValueError:
            raise ValidationError(
                {"targets": ["Use lang:count pairs, e.g. en:3,fr:2"]}, code="invalid_targets"
            )
    return result


def project_session(
    user,
    *,
    targets: Mapping[str, int],
    session_date: dt.date | None = None,
    categories=None,
) -> SessionProjection:
    session_date = session_date or user.local_today()
    projection = SessionProjection()
    for profile in account_services.active_profiles(user):
        code = profile.language
        target = int(targets.get(code, 0))
        available = carried_over_cards(user, code).count()
        carried = min(target, available)
        to_generate = max(0, target - carried) if categories else 0
        due_qs = queue.due_cards(user, session_date, language=code)
        projection.languages.append(
            LanguageProjection(
                language=code,
                base_level=band_for_rating(profile.level_rating),
                carried_over=carried,
                available_carry_over=available,
                to_generate=to_generate,
                probes=probe_count(to_generate),
                due_today=due_qs.count(),
                overdue=due_qs.filter(scheduler__due_date__lt=session_date).count(),
            )
        )
    return projection


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


# --- Creation ---------------------------------------------------------------------------------


def create_session(user, *, category_ids, new_cards_targets: Mapping[str, int]) -> DailySession:
    session_date = user.local_today()
    existing = DailySession.objects.filter(session_date=session_date).first()
    if existing is not None:
        raise ConflictError(
            "A session already exists for today.",
            code="session_exists",
            extra={"session_id": str(existing.id)},
        )
    targets = resolve_targets(user, new_cards_targets)
    categories = resolve_categories(user, category_ids)
    if sum(targets.values()) > 0 and not categories:
        from rest_framework.exceptions import ValidationError

        raise ValidationError(
            {"category_ids": ["Choose at least one category to generate new cards."]},
            code="no_categories",
        )

    from apps.practice.tasks import generate_session_cards

    profiles = {p.language: p for p in account_services.active_profiles(user)}
    with transaction.atomic():
        session = DailySession.objects.create(
            user=user, session_date=session_date, status=SessionStatus.GENERATING
        )
        session.categories.set(categories)
        position = 0
        needs_generation = False
        for code, target in targets.items():
            carried = list(carried_over_cards(user, code)[:target])
            SessionNewCard.objects.bulk_create(
                [
                    SessionNewCard(
                        user=user,
                        session=session,
                        card=card,
                        position=position + offset,
                        origin=NewCardOrigin.CARRIED_OVER,
                    )
                    for offset, card in enumerate(carried, start=1)
                ]
            )
            position += len(carried)
            to_generate = max(0, target - len(carried)) if categories else 0
            SessionLanguagePlan.objects.create(
                user=user,
                session=session,
                language=code,
                new_cards_target=target,
                rating_at_start=profiles[code].level_rating,
                generation_status=PlanStatus.PENDING if to_generate else PlanStatus.READY,
            )
            needs_generation = needs_generation or to_generate > 0
        if needs_generation:
            from apps.core.tasks import enqueue

            enqueue(generate_session_cards, session_id=str(session.id), user_id=str(user.id))
        else:
            session.status = SessionStatus.READY
            session.save(update_fields=["status", "updated_at"])
    session.refresh_from_db()
    return session


# --- Generation -------------------------------------------------------------------------------


def normalise_question(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def next_position(session: DailySession) -> int:
    current = SessionNewCard.objects.filter(session=session).aggregate(m=Max("position"))["m"]
    return (current or 0) + 1


def _finish_session(session: DailySession) -> None:
    plans = list(session.plans.all())
    failed = [p for p in plans if p.generation_status == PlanStatus.FAILED]
    if failed:
        session.status = SessionStatus.FAILED
        session.generation_error = "; ".join(f"{p.language}: {p.generation_error}" for p in failed)
    else:
        session.status = SessionStatus.READY
        session.generation_error = ""
    session.save(update_fields=["status", "generation_error", "updated_at"])


def run_generation(session: DailySession) -> list[Card]:
    """Generate the missing new cards for every pending plan. Runs inside the owner context."""
    categories = list(session.categories.all().order_by("sort_order", "name"))
    created: list[Card] = []
    for plan in session.plans.filter(generation_status=PlanStatus.PENDING).order_by("language"):
        created.extend(_generate_for_plan(session, plan, categories))
    _finish_session(session)
    return created


def _generate_for_plan(
    session: DailySession, plan: SessionLanguagePlan, categories: list[Category]
) -> list[Card]:
    user = session.user
    language = plan.language
    carried = SessionNewCard.objects.filter(session=session, card__language=language).count()
    to_generate = max(0, plan.new_cards_target - carried)
    if to_generate == 0 or not categories:
        plan.generation_status = PlanStatus.READY
        plan.save(update_fields=["generation_status", "updated_at"])
        return []

    base_level = band_for_rating(plan.rating_at_start)
    slots = plan_slots(to_generate, categories, base_level)
    recent = list(
        Card.objects.filter(language=language, category__in=categories)
        .order_by("-created_at")
        .values_list("category__slug", "question_text")[: settings.ECHO_GENERATION_RECENT_QUESTIONS]
    )
    try:
        result = ai_services.generate_questions(
            user=user,
            language=get_language(language),
            slots=slots,
            categories=categories,
            recent_questions=recent,
            related=plan,
        )
    except AIError as exc:
        plan.generation_status = PlanStatus.FAILED
        plan.generation_error = str(exc)[:1000]
        plan.save(update_fields=["generation_status", "generation_error", "updated_at"])
        return []

    by_slot = {q.slot: q for q in result.parsed.questions}
    existing = {
        normalise_question(t)
        for t in Card.objects.filter(language=language).values_list("question_text", flat=True)
    }
    created: list[Card] = []
    with transaction.atomic():
        position = next_position(session) - 1
        for slot in slots:
            question = by_slot.get(slot.number)
            if question is None:
                log.warning(
                    "generation: slot %s missing in response (session=%s, lang=%s)",
                    slot.number,
                    session.id,
                    language,
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
                language=language,
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
            # Spoken question, generated off the request path; the card works without it.
            enqueue(synthesize_question_audio, card_id=str(card.id), user_id=str(user.id))
            created.append(card)
        if not created:
            plan.generation_status = PlanStatus.FAILED
            plan.generation_error = "The generator returned no usable questions."
        else:
            plan.generation_status = PlanStatus.READY
            plan.generation_error = ""
            plan.generated_count += len(created)
        plan.save(
            update_fields=["generation_status", "generation_error", "generated_count", "updated_at"]
        )
    return created


def retry_generation(session: DailySession) -> DailySession:
    if session.status != SessionStatus.FAILED:
        raise ConflictError("Only failed sessions can be retried.", code="not_failed")
    from apps.practice.tasks import generate_session_cards

    session.plans.filter(generation_status=PlanStatus.FAILED).update(
        generation_status=PlanStatus.PENDING, generation_error=""
    )
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
