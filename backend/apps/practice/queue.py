"""The day's queue: new cards (by position) then due cards, computed live (§4.2).

Every function takes an optional `language`; without it the queue covers the learner's
*active* languages (paused ones disappear immediately, see the multi-language addendum).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from django.db.models import Count, Q

from apps.accounts import services as account_services
from apps.cards.models import Card, CardStatus
from apps.practice.models import DailySession, SessionNewCard
from apps.scheduling.models import Maturity, ReviewLog


@dataclass
class QueueItem:
    kind: str  # new | due
    card: Card
    position: int | None = None
    origin: str | None = None
    due_date: dt.date | None = None


def _annotate_attempts(qs):
    return qs.annotate(attempt_count=Count("attempts", filter=Q(attempts__status="completed")))


def _languages(user, language: str | None) -> list[str]:
    """Active languages, or just `language` when it is active (a paused one yields nothing)."""
    active = account_services.active_language_codes(user)
    if language is None:
        return active
    return [language] if language in active else []


def new_items(session: DailySession, language: str | None = None) -> list[QueueItem]:
    slots = (
        SessionNewCard.objects.filter(
            session=session,
            card__status=CardStatus.ACTIVE,
            card__scheduler__maturity=Maturity.NEW,
            card__language__in=_languages(session.user, language),
        )
        .select_related("card", "card__category", "card__scheduler")
        .order_by("position")
    )
    cards = {
        c.id: c for c in _annotate_attempts(Card.objects.filter(pk__in=[s.card_id for s in slots]))
    }
    items = []
    for slot in slots:
        card = cards.get(slot.card_id, slot.card)
        card.scheduler = slot.card.scheduler
        card.category = slot.card.category
        items.append(QueueItem(kind="new", card=card, position=slot.position, origin=slot.origin))
    return items


def due_cards(user, session_date: dt.date, language: str | None = None):
    return _annotate_attempts(
        Card.objects.filter(
            status=CardStatus.ACTIVE,
            scheduler__due_date__lte=session_date,
            language__in=_languages(user, language),
        )
        .exclude(scheduler__maturity=Maturity.NEW)
        .select_related("category", "scheduler")
        .order_by("scheduler__due_date", "scheduler__ease_factor", "created_at")
    )


def due_items(session: DailySession, language: str | None = None) -> list[QueueItem]:
    return [
        QueueItem(kind="due", card=card, due_date=card.scheduler.due_date)
        for card in due_cards(session.user, session.session_date, language)
    ]


def build_queue(session: DailySession, language: str | None = None) -> list[QueueItem]:
    return new_items(session, language) + due_items(session, language)


def progress(session: DailySession, language: str | None = None) -> dict:
    languages = _languages(session.user, language)
    new_qs = SessionNewCard.objects.filter(session=session, card__language__in=languages)
    new_total = new_qs.count()
    new_remaining = new_qs.filter(
        card__status=CardStatus.ACTIVE, card__scheduler__maturity=Maturity.NEW
    ).count()
    due_done = (
        ReviewLog.objects.filter(
            reviewed_on=session.session_date,
            due_before__lte=session.session_date,
            card__language__in=languages,
        )
        .exclude(maturity_before=Maturity.NEW)
        .count()
    )
    due_remaining = due_cards(session.user, session.session_date, language).count()
    return {
        "new_total": new_total,
        "new_done": new_total - new_remaining,
        "due_total": due_remaining + due_done,
        "due_done": due_done,
        "remaining": new_remaining + due_remaining,
    }
