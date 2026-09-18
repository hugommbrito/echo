from __future__ import annotations

from django.db import models

from apps.core.models import OwnedModel


class LevelLog(OwnedModel):
    """One row per attempt that moved the learner's rating."""

    attempt = models.OneToOneField(
        "practice.Attempt", on_delete=models.CASCADE, related_name="level_change"
    )
    card = models.ForeignKey("cards.Card", on_delete=models.CASCADE, related_name="level_logs")
    logged_on = models.DateField()
    rating_before = models.IntegerField()
    rating_after = models.IntegerField()
    delta = models.IntegerField()
    question_rating = models.IntegerField()
    expected = models.DecimalField(max_digits=4, decimal_places=3)
    actual = models.DecimalField(max_digits=4, decimal_places=3)
    k_factor = models.PositiveSmallIntegerField()
    level_version = models.CharField(max_length=20)

    class Meta(OwnedModel.Meta):
        ordering = ["-logged_on", "-created_at"]
        indexes = [models.Index(fields=["user", "logged_on"])]
