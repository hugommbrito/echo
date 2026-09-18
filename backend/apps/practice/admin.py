from django.contrib import admin

from apps.core.admin import OwnedModelAdmin
from apps.practice.models import Attempt, DailySession, Evaluation, SessionNewCard


class SessionNewCardInline(admin.TabularInline):
    model = SessionNewCard
    extra = 0
    fields = ["position", "card", "origin"]
    readonly_fields = fields

    def get_queryset(self, request):
        return SessionNewCard.all_users.select_related("card")


@admin.register(DailySession)
class DailySessionAdmin(OwnedModelAdmin):
    list_display = ["session_date", "status", "new_cards_target", "rating_at_start", "completed_at"]
    list_filter = ["status", "session_date"]
    inlines = [SessionNewCardInline]


@admin.register(Attempt)
class AttemptAdmin(OwnedModelAdmin):
    list_display = [
        "created_at",
        "card",
        "attempt_number",
        "status",
        "failure_stage",
        "counts_for_scheduling",
        "audio_duration_seconds",
        "word_count",
    ]
    list_filter = ["status", "counts_for_scheduling", "insufficient_speech"]
    readonly_fields = [
        f.name
        for f in Attempt._meta.fields
        if f.name not in {"status", "failure_stage", "error_message"}
    ]


@admin.register(Evaluation)
class EvaluationAdmin(OwnedModelAdmin):
    list_display = [
        "created_at",
        "attempt",
        "structure_score",
        "grammar_score",
        "fluency_score",
        "composite_score",
        "sm2_quality",
        "model",
    ]
    readonly_fields = [f.name for f in Evaluation._meta.fields]
