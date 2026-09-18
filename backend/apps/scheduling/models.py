from __future__ import annotations

from decimal import Decimal

from django.db import models

from apps.core.models import OwnedModel


class Maturity(models.TextChoices):
    NEW = "new", "New"
    LEARNING = "learning", "Learning"
    MATURE = "mature", "Mature"


class SchedulerState(OwnedModel):
    """SM-2 state of one card. `due_date` is null while the card is `new`."""

    card = models.OneToOneField("cards.Card", on_delete=models.CASCADE, related_name="scheduler")
    maturity = models.CharField(max_length=10, choices=Maturity.choices, default=Maturity.NEW)
    ease_factor = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("2.50"))
    interval_days = models.PositiveIntegerField(default=0)
    repetitions = models.PositiveIntegerField(default=0)
    lapses = models.PositiveIntegerField(default=0)
    total_reviews = models.PositiveIntegerField(default=0)
    due_date = models.DateField(null=True, blank=True)
    last_reviewed_on = models.DateField(null=True, blank=True)
    last_quality = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta(OwnedModel.Meta):
        indexes = [
            models.Index(fields=["user", "due_date"]),
            models.Index(fields=["user", "maturity"]),
        ]

    def __str__(self) -> str:
        return f"{self.card_id} {self.maturity} due={self.due_date}"


class ReviewLog(OwnedModel):
    """One row per application of the scheduler (first completed attempt of the day)."""

    card = models.ForeignKey("cards.Card", on_delete=models.CASCADE, related_name="review_logs")
    attempt = models.OneToOneField(
        "practice.Attempt", on_delete=models.CASCADE, related_name="review"
    )
    reviewed_on = models.DateField()
    quality = models.PositiveSmallIntegerField()
    composite_score = models.DecimalField(max_digits=3, decimal_places=2)
    ease_before = models.DecimalField(max_digits=4, decimal_places=2)
    ease_after = models.DecimalField(max_digits=4, decimal_places=2)
    interval_before = models.PositiveIntegerField()
    interval_after = models.PositiveIntegerField()
    due_before = models.DateField(null=True, blank=True)
    due_after = models.DateField()
    maturity_before = models.CharField(max_length=10, choices=Maturity.choices)
    maturity_after = models.CharField(max_length=10, choices=Maturity.choices)
    scheduler_version = models.CharField(max_length=20)

    class Meta(OwnedModel.Meta):
        ordering = ["-reviewed_on", "-created_at"]
        indexes = [models.Index(fields=["user", "reviewed_on"])]
