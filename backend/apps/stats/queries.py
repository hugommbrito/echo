"""Dashboard aggregates (docs/PLAN.md §6.6 and §10). All dates are the learner's local dates.

Volumes are small (tens of attempts a day), so most grouping happens in Python over the
scoped querysets — simpler, portable across SQLite/Postgres and easy to verify by hand.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from statistics import mean

from django.db.models import Count, Sum

from apps.cards.models import Card, CardStatus, Category
from apps.leveling.elo import band_for_rating, bands_for_api, is_provisional
from apps.leveling.models import LevelLog
from apps.practice.models import Attempt, AttemptStatus, DailySession, Evaluation
from apps.scheduling.models import Maturity, ReviewLog, SchedulerState

DEFAULT_PERIOD_DAYS = 30


@dataclass(frozen=True)
class Period:
    start: dt.date
    end: dt.date  # inclusive

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def previous(self) -> Period:
        return Period(self.start - dt.timedelta(days=self.days), self.start - dt.timedelta(days=1))

    def as_dict(self) -> dict:
        return {"from": self.start, "to": self.end, "days": self.days}


def parse_period(user, raw_from: str | None, raw_to: str | None) -> Period:
    today = user.local_today()
    end = dt.date.fromisoformat(raw_to) if raw_to else today
    start = (
        dt.date.fromisoformat(raw_from)
        if raw_from
        else end - dt.timedelta(days=DEFAULT_PERIOD_DAYS - 1)
    )
    if start > end:
        start, end = end, start
    return Period(start, end)


def resolve_category(user, raw: str | None) -> Category | None:
    if not raw:
        return None
    qs = Category.objects.visible_to(user)
    try:
        import uuid

        uuid.UUID(str(raw))
        return qs.filter(pk=raw).first()
    except ValueError:
        return qs.filter(slug=raw).first()


def _q2(value) -> float | None:
    """Stats return plain numbers (rounded to 2 places) — handier for charts than strings."""
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _avg(values) -> float | None:
    values = [Decimal(str(v)) for v in values if v is not None]
    return _q2(mean(values)) if values else None


def week_start(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def bucket_start(day: dt.date, bucket: str) -> dt.date:
    return week_start(day) if bucket == "week" else day


# --- Building blocks ------------------------------------------------------------------------


def scored_attempts(period: Period, category: Category | None):
    qs = Evaluation.objects.filter(
        attempt__status=AttemptStatus.COMPLETED,
        attempt__insufficient_speech=False,
        attempt__attempted_on__gte=period.start,
        attempt__attempted_on__lte=period.end,
    ).select_related("attempt", "attempt__card")
    if category is not None:
        qs = qs.filter(attempt__card__category=category)
    return qs


def score_summary(period: Period, category: Category | None) -> dict:
    rows = list(
        scored_attempts(period, category).values_list(
            "structure_score", "grammar_score", "fluency_score", "composite_score"
        )
    )
    return {
        "structure_avg": _avg(r[0] for r in rows),
        "grammar_avg": _avg(r[1] for r in rows),
        "fluency_avg": _avg(r[2] for r in rows),
        "composite_avg": _avg(r[3] for r in rows),
        "attempts": len(rows),
    }


def active_states(category: Category | None = None):
    qs = SchedulerState.objects.filter(card__status=CardStatus.ACTIVE)
    if category is not None:
        qs = qs.filter(card__category=category)
    return qs


# --- Endpoints ------------------------------------------------------------------------------


def overview(user, period: Period, category: Category | None) -> dict:
    today = user.local_today()
    reviews_today = ReviewLog.objects.filter(reviewed_on=today)
    session_today = DailySession.objects.filter(session_date=today).first()
    states = active_states()
    due_qs = states.exclude(maturity=Maturity.NEW)

    level_logs = LevelLog.objects.filter(
        logged_on__gte=period.start, logged_on__lte=period.end
    ).order_by("logged_on", "created_at")
    first_log = level_logs.first()
    delta_period = user.level_rating - first_log.rating_before if first_log else 0
    band = band_for_rating(user.level_rating)
    next_band = next((b for b in bands_for_api() if b["min"] > user.level_rating), None)

    return {
        "period": period.as_dict(),
        "today": {
            "answered": Attempt.objects.filter(
                attempted_on=today, status=AttemptStatus.COMPLETED, counts_for_scheduling=True
            ).count(),
            "new_answered": reviews_today.filter(maturity_before=Maturity.NEW).count(),
            "due_answered": reviews_today.exclude(maturity_before=Maturity.NEW).count(),
            "target": session_today.new_cards_target
            if session_today
            else user.default_new_cards_per_day,
            "session_id": str(session_today.id) if session_today else None,
            "session_status": session_today.status if session_today else None,
        },
        "due": {
            "today": due_qs.filter(due_date__lte=today).count(),
            "overdue": due_qs.filter(due_date__lt=today).count(),
            "next_7_days": due_qs.filter(
                due_date__gt=today, due_date__lte=today + dt.timedelta(days=7)
            ).count(),
        },
        "collection": {
            "total": states.count(),
            "new": states.filter(maturity=Maturity.NEW).count(),
            "learning": states.filter(maturity=Maturity.LEARNING).count(),
            "mature": states.filter(maturity=Maturity.MATURE).count(),
            "suspended": Card.objects.filter(status=CardStatus.SUSPENDED).count(),
        },
        "scores": {
            "period": score_summary(period, category),
            "previous_period": score_summary(period.previous(), category),
        },
        "level": {
            "rating": user.level_rating,
            "band": band,
            "delta_period": delta_period,
            "provisional": is_provisional(user.counted_attempts),
            "counted_attempts": user.counted_attempts,
            "initial_rating": user.level_rating_initial or user.level_rating,
            "next_band": {
                "label": next_band["label"],
                "points_needed": next_band["min"] - user.level_rating,
            }
            if next_band
            else None,
        },
    }


def scores(period: Period, category: Category | None, bucket: str) -> list[dict]:
    grouped: dict[dt.date, list] = defaultdict(list)
    for ev in scored_attempts(period, category):
        grouped[bucket_start(ev.attempt.attempted_on, bucket)].append(ev)
    return [
        {
            "bucket_start": start,
            "structure_avg": _avg(e.structure_score for e in items),
            "grammar_avg": _avg(e.grammar_score for e in items),
            "fluency_avg": _avg(e.fluency_score for e in items),
            "composite_avg": _avg(e.composite_score for e in items),
            "attempts": len(items),
        }
        for start, items in sorted(grouped.items())
    ]


def level(user, period: Period) -> dict:
    logs = list(
        LevelLog.objects.filter(logged_on__gte=period.start, logged_on__lte=period.end)
        .select_related("card")
        .order_by("logged_on", "created_at")
    )
    last_per_day: dict[dt.date, int] = {}
    for log in logs:
        last_per_day[log.logged_on] = log.rating_after
    points = [{"date": day, "rating_after": rating} for day, rating in sorted(last_per_day.items())]
    start_rating = logs[0].rating_before if logs else user.level_rating
    if not points or points[0]["date"] != period.start:
        points.insert(0, {"date": period.start, "rating_after": start_rating})

    probes: dict[str, dict] = {}
    for kind in ("above", "below"):
        kind_logs = [log for log in logs if log.card.probe == kind]
        hits = sum(1 for log in kind_logs if log.actual >= Decimal("0.5"))
        probes[kind] = {
            "answered": len(kind_logs),
            "hits": hits,
            "avg_actual": _avg(log.actual for log in kind_logs),
            "avg_delta": _q2(mean(log.delta for log in kind_logs)) if kind_logs else None,
        }

    return {
        "period": period.as_dict(),
        "points": points,
        "bands": bands_for_api(),
        "probes": probes,
        "events": [
            {
                "date": log.logged_on,
                "delta": log.delta,
                "rating_after": log.rating_after,
                "probe": log.card.probe,
                "hit": log.actual >= Decimal("0.5"),
            }
            for log in logs
            if log.card.probe != "none"
        ],
        "current": {"rating": user.level_rating, "band": band_for_rating(user.level_rating)},
        "initial_rating": user.level_rating_initial or user.level_rating,
    }


def activity(period: Period, category: Category | None, bucket: str) -> list[dict]:
    reviews = ReviewLog.objects.filter(reviewed_on__gte=period.start, reviewed_on__lte=period.end)
    attempts = Attempt.objects.filter(
        status=AttemptStatus.COMPLETED, attempted_on__gte=period.start, attempted_on__lte=period.end
    )
    if category is not None:
        reviews = reviews.filter(card__category=category)
        attempts = attempts.filter(card__category=category)
    counts: dict[dt.date, Counter] = defaultdict(Counter)
    for reviewed_on, maturity_before in reviews.values_list("reviewed_on", "maturity_before"):
        counts[bucket_start(reviewed_on, bucket)][maturity_before] += 1
    seconds: dict[dt.date, Decimal] = defaultdict(Decimal)
    for attempted_on, duration in attempts.values_list("attempted_on", "audio_duration_seconds"):
        seconds[bucket_start(attempted_on, bucket)] += duration or 0
    keys = sorted(set(counts) | set(seconds))
    return [
        {
            "bucket_start": key,
            "new": counts[key]["new"],
            "learning": counts[key]["learning"],
            "mature": counts[key]["mature"],
            "total": sum(counts[key].values()),
            "speaking_seconds": int(seconds[key]),
        }
        for key in keys
    ]


def forecast(user, days: int) -> dict:
    today = user.local_today()
    horizon = today + dt.timedelta(days=days)
    due_qs = active_states().exclude(maturity=Maturity.NEW)
    overdue = due_qs.filter(due_date__lt=today).count()
    per_day = Counter(
        due_qs.filter(due_date__gte=today, due_date__lt=horizon).values_list("due_date", flat=True)
    )
    rows = []
    for offset in range(days):
        day = today + dt.timedelta(days=offset)
        rows.append({"date": day, "due": per_day.get(day, 0) + (overdue if offset == 0 else 0)})
    return {"days": rows, "overdue": overdue, "total": overdue + sum(per_day.values())}


def collection(user) -> dict:
    states = active_states()
    by_maturity = {
        "new": states.filter(maturity=Maturity.NEW).count(),
        "learning": states.filter(maturity=Maturity.LEARNING).count(),
        "mature": states.filter(maturity=Maturity.MATURE).count(),
        "suspended": Card.objects.filter(status=CardStatus.SUSPENDED).count(),
    }
    by_category_rows = (
        states.values(
            "card__category_id", "card__category__slug", "card__category__name", "maturity"
        )
        .annotate(count=Count("id"))
        .order_by("card__category__sort_order", "card__category__name")
    )
    per_category: dict = {}
    for row in by_category_rows:
        entry = per_category.setdefault(
            row["card__category_id"],
            {
                "category": {
                    "id": str(row["card__category_id"]),
                    "slug": row["card__category__slug"],
                    "name": row["card__category__name"],
                },
                "new": 0,
                "learning": 0,
                "mature": 0,
                "total": 0,
            },
        )
        entry[row["maturity"]] += row["count"]
        entry["total"] += row["count"]
    by_level = Counter(
        Card.objects.filter(status=CardStatus.ACTIVE).values_list("cefr_level", flat=True)
    )
    return {
        "by_maturity": by_maturity,
        "by_category": sorted(per_category.values(), key=lambda e: -e["total"]),
        "by_level": [
            {"level": lvl, "count": by_level.get(lvl, 0)}
            for lvl in ["A1", "A2", "B1", "B2", "C1", "C2"]
        ],
    }


def grammar_issues(period: Period, category: Category | None) -> dict:
    def collect(p: Period) -> tuple[Counter, dict[str, list]]:
        counts: Counter = Counter()
        examples: dict[str, list] = defaultdict(list)
        for issues in scored_attempts(p, category).values_list("grammar_issues", flat=True):
            for issue in issues or []:
                kind = issue.get("type", "other")
                counts[kind] += 1
                if len(examples[kind]) < 3:
                    examples[kind].append(
                        {"quote": issue.get("quote", ""), "correction": issue.get("correction", "")}
                    )
        return counts, examples

    current, examples = collect(period)
    previous, _ = collect(period.previous())
    items = [
        {
            "type": kind,
            "count": count,
            "previous_count": previous.get(kind, 0),
            "delta": count - previous.get(kind, 0),
            "examples": examples[kind],
        }
        for kind, count in current.most_common()
    ]
    return {
        "period": period.as_dict(),
        "items": items,
        "total": sum(current.values()),
        "previous_total": sum(previous.values()),
    }


def categories(user, period: Period) -> list[dict]:
    cards_by_category = Counter(
        Card.objects.filter(status=CardStatus.ACTIVE).values_list("category_id", flat=True)
    )
    evaluations = list(scored_attempts(period, None))
    grouped: dict = defaultdict(list)
    for ev in evaluations:
        grouped[ev.attempt.card.category_id].append(ev)
    rows = []
    for cat in Category.objects.visible_to(user).order_by("sort_order", "name"):
        evs = grouped.get(cat.id, [])
        if not evs and not cards_by_category.get(cat.id):
            continue
        weekly: dict[dt.date, list] = defaultdict(list)
        for ev in evs:
            weekly[week_start(ev.attempt.attempted_on)].append(ev.composite_score)
        rows.append(
            {
                "category": {
                    "id": str(cat.id),
                    "slug": cat.slug,
                    "name": cat.name,
                    "scope": cat.scope,
                },
                "cards": cards_by_category.get(cat.id, 0),
                "attempts": len(evs),
                "structure_avg": _avg(e.structure_score for e in evs),
                "grammar_avg": _avg(e.grammar_score for e in evs),
                "fluency_avg": _avg(e.fluency_score for e in evs),
                "composite_avg": _avg(e.composite_score for e in evs),
                "trend": [
                    {"week_start": w, "composite_avg": _avg(v)} for w, v in sorted(weekly.items())
                ][-8:],
            }
        )
    return rows


def heatmap(user, year: int, category: Category | None) -> list[dict]:
    qs = Attempt.objects.filter(status=AttemptStatus.COMPLETED, attempted_on__year=year)
    if category is not None:
        qs = qs.filter(card__category=category)
    rows = (
        qs.values("attempted_on")
        .annotate(count=Count("id"), seconds=Sum("audio_duration_seconds"))
        .order_by("attempted_on")
    )
    return [
        {"date": r["attempted_on"], "count": r["count"], "speaking_seconds": int(r["seconds"] or 0)}
        for r in rows
    ]


def advanced(user) -> dict:
    """Ease and interval distributions + answer durations (the collapsed 'Avançado' block)."""
    states = active_states().exclude(maturity=Maturity.NEW)
    ease_buckets = Counter()
    interval_buckets = Counter()
    for ease, interval in states.values_list("ease_factor", "interval_days"):
        ease_buckets[str(Decimal(ease).quantize(Decimal("0.1")))] += 1
        if interval <= 7:
            interval_buckets["1-7"] += 1
        elif interval <= 30:
            interval_buckets["8-30"] += 1
        elif interval <= 90:
            interval_buckets["31-90"] += 1
        else:
            interval_buckets["91-180"] += 1
    durations = list(
        Attempt.objects.filter(
            status=AttemptStatus.COMPLETED, audio_duration_seconds__isnull=False
        ).values_list("audio_duration_seconds", flat=True)
    )
    return {
        "ease": [{"ease": k, "count": v} for k, v in sorted(ease_buckets.items())],
        "intervals": [
            {"range": k, "count": interval_buckets.get(k, 0)}
            for k in ["1-7", "8-30", "31-90", "91-180"]
        ],
        "answer_duration": {
            "avg_seconds": int(mean(durations)) if durations else None,
            "min_seconds": int(min(durations)) if durations else None,
            "max_seconds": int(max(durations)) if durations else None,
            "attempts": len(durations),
        },
    }
