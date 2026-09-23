from __future__ import annotations

from django.db import models

from apps.core.languages import LanguageCode
from apps.core.models import OwnedModel
from apps.core.storage import attempt_audio_path


class SessionStatus(models.TextChoices):
    GENERATING = "generating", "Generating"
    READY = "ready", "Ready"
    IN_PROGRESS = "in_progress", "In progress"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class PlanStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"


class NewCardOrigin(models.TextChoices):
    GENERATED = "generated", "Generated"
    CARRIED_OVER = "carried_over", "Carried over"


class AttemptStatus(models.TextChoices):
    UPLOADED = "uploaded", "Uploaded"
    PROBING = "probing", "Probing audio"
    TRANSCRIBING = "transcribing", "Transcribing"
    EVALUATING = "evaluating", "Evaluating"
    SCHEDULING = "scheduling", "Scheduling"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


PIPELINE_STAGES = ["probing", "transcribing", "evaluating", "scheduling"]


class DailySession(OwnedModel):
    session_date = models.DateField()
    categories = models.ManyToManyField("cards.Category", related_name="sessions", blank=True)
    status = models.CharField(
        max_length=12, choices=SessionStatus.choices, default=SessionStatus.GENERATING
    )
    generation_error = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta(OwnedModel.Meta):
        ordering = ["-session_date"]
        constraints = [
            models.UniqueConstraint(fields=["user", "session_date"], name="uniq_session_per_day")
        ]

    def __str__(self) -> str:
        return f"{self.user_id} {self.session_date} ({self.status})"

    @property
    def new_cards_target_total(self) -> int:
        return sum(plan.new_cards_target for plan in self.plans.all())


class SessionLanguagePlan(OwnedModel):
    """Per-language part of a daily session: target, rating snapshot and generation state."""

    session = models.ForeignKey(DailySession, on_delete=models.CASCADE, related_name="plans")
    language = models.CharField(max_length=8, choices=LanguageCode.choices)
    new_cards_target = models.PositiveSmallIntegerField()
    rating_at_start = models.IntegerField()
    generation_status = models.CharField(
        max_length=8, choices=PlanStatus.choices, default=PlanStatus.PENDING
    )
    generation_error = models.TextField(blank=True)
    generated_count = models.PositiveSmallIntegerField(default=0)

    class Meta(OwnedModel.Meta):
        ordering = ["language"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "session", "language"], name="uniq_session_language_plan"
            )
        ]

    def __str__(self) -> str:
        return f"{self.session_id} {self.language} x{self.new_cards_target}"


class SessionNewCard(OwnedModel):
    session = models.ForeignKey(DailySession, on_delete=models.CASCADE, related_name="new_cards")
    card = models.ForeignKey("cards.Card", on_delete=models.CASCADE, related_name="session_slots")
    position = models.PositiveSmallIntegerField()
    origin = models.CharField(max_length=12, choices=NewCardOrigin.choices)

    class Meta(OwnedModel.Meta):
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["user", "session", "card"], name="uniq_session_card")
        ]


class Attempt(OwnedModel):
    card = models.ForeignKey("cards.Card", on_delete=models.CASCADE, related_name="attempts")
    session = models.ForeignKey(
        DailySession, null=True, blank=True, on_delete=models.SET_NULL, related_name="attempts"
    )
    attempt_number = models.PositiveSmallIntegerField()
    attempted_on = models.DateField()  # the learner's local date
    counts_for_scheduling = models.BooleanField(default=False)
    insufficient_speech = models.BooleanField(default=False)

    audio_file = models.FileField(upload_to=attempt_audio_path, max_length=255)
    audio_mime = models.CharField(max_length=100)
    audio_size_bytes = models.PositiveIntegerField(default=0)
    client_duration_seconds = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    audio_duration_seconds = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )

    status = models.CharField(
        max_length=14, choices=AttemptStatus.choices, default=AttemptStatus.UPLOADED
    )
    failure_stage = models.CharField(max_length=14, blank=True)
    error_message = models.TextField(blank=True)

    transcript_text = models.TextField(blank=True)
    transcript_segments = models.JSONField(default=list, blank=True)
    word_count = models.PositiveIntegerField(null=True, blank=True)
    words_per_minute = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    transcription_model = models.CharField(max_length=60, blank=True)

    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta(OwnedModel.Meta):
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "card", "attempt_number"], name="uniq_card_attempt_no"
            )
        ]
        indexes = [
            models.Index(fields=["user", "attempted_on"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self) -> str:
        return f"attempt #{self.attempt_number} on {self.card_id} ({self.status})"

    @property
    def is_completed(self) -> bool:
        return self.status == AttemptStatus.COMPLETED


class Evaluation(OwnedModel):
    attempt = models.OneToOneField(Attempt, on_delete=models.CASCADE, related_name="evaluation")

    structure_score = models.PositiveSmallIntegerField()
    grammar_score = models.PositiveSmallIntegerField()
    fluency_score = models.PositiveSmallIntegerField()
    structure_feedback = models.TextField(blank=True)
    grammar_feedback = models.TextField(blank=True)
    fluency_feedback = models.TextField(blank=True)
    grammar_issues = models.JSONField(default=list, blank=True)
    fluency_markers = models.JSONField(default=dict, blank=True)

    composite_score = models.DecimalField(max_digits=3, decimal_places=2)
    sm2_quality = models.PositiveSmallIntegerField()

    improved_answer = models.TextField(null=True, blank=True)
    improved_answer_notes = models.JSONField(default=list, blank=True)
    improved_answer_model = models.CharField(max_length=80, blank=True)
    improved_answer_generated_at = models.DateTimeField(null=True, blank=True)

    model = models.CharField(max_length=80)
    prompt_version = models.CharField(max_length=20)
    raw_response = models.JSONField(default=dict, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)

    class Meta(OwnedModel.Meta):
        ordering = ["-created_at"]
