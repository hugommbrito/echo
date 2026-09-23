from __future__ import annotations

from django.db import models

from apps.core.models import OwnedModel


class AIRequestKind(models.TextChoices):
    GENERATE_QUESTIONS = "generate_questions", "Generate questions"
    TRANSCRIBE = "transcribe", "Transcribe"
    EVALUATE = "evaluate", "Evaluate"
    IMPROVE_ANSWER = "improve_answer", "Improve answer"


class AIRequestStatus(models.TextChoices):
    OK = "ok", "OK"
    ERROR = "error", "Error"


class AIRequestLog(OwnedModel):
    kind = models.CharField(max_length=20, choices=AIRequestKind.choices)
    provider = models.CharField(max_length=20)
    model = models.CharField(max_length=80)
    language = models.CharField(max_length=8, blank=True, default="")
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cache_read_input_tokens = models.PositiveIntegerField(default=0)
    cache_creation_input_tokens = models.PositiveIntegerField(default=0)
    audio_seconds = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    estimated_cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=8, choices=AIRequestStatus.choices)
    error = models.TextField(blank=True)
    related_object_type = models.CharField(max_length=40, blank=True)
    related_object_id = models.UUIDField(null=True, blank=True)

    class Meta(OwnedModel.Meta):
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "created_at"]), models.Index(fields=["kind"])]
