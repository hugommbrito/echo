"""Slot planning for question generation: category round-robin + probe policy (§4.7.3)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

from apps.leveling.elo import shift_level


@dataclass(frozen=True)
class Slot:
    number: int  # 1-based, as shown to the generator
    category: object  # cards.Category
    level: str
    probe: str  # none | above | below


def probe_count(to_generate: int) -> int:
    if to_generate <= 0:
        return 0
    raw = (Decimal(to_generate) * Decimal(str(settings.ECHO_PROBE_RATIO))).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    count = int(raw)
    if to_generate >= settings.ECHO_PROBE_MIN_GENERATED_FOR_PROBE:
        count = max(1, count)
    return min(count, to_generate)


def probe_positions(to_generate: int, n_probes: int) -> list[int]:
    """0-based slot indexes for probes, evenly spread across the batch."""
    if n_probes == 0:
        return []
    step = to_generate / n_probes
    return [min(to_generate - 1, int(step * i + step / 2)) for i in range(n_probes)]


def plan_slots(to_generate: int, categories: Sequence, base_level: str) -> list[Slot]:
    if to_generate <= 0 or not categories:
        return []
    positions = set(probe_positions(to_generate, probe_count(to_generate)))
    slots: list[Slot] = []
    direction_above = True  # alternate, starting with "above"
    for index in range(to_generate):
        category = categories[index % len(categories)]
        level, probe = base_level, "none"
        if index in positions:
            wanted = "above" if direction_above else "below"
            direction_above = not direction_above
            shifted = shift_level(base_level, +1 if wanted == "above" else -1)
            if shifted is None:  # edge of the scale: flip the direction instead of dropping it
                wanted = "below" if wanted == "above" else "above"
                shifted = shift_level(base_level, +1 if wanted == "above" else -1)
            if shifted is not None:
                level, probe = shifted, wanted
        slots.append(Slot(number=index + 1, category=category, level=level, probe=probe))
    return slots
