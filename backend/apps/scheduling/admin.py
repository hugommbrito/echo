from django.contrib import admin

from apps.core.admin import OwnedModelAdmin
from apps.scheduling.models import ReviewLog, SchedulerState


@admin.register(SchedulerState)
class SchedulerStateAdmin(OwnedModelAdmin):
    list_display = [
        "card",
        "maturity",
        "ease_factor",
        "interval_days",
        "repetitions",
        "lapses",
        "due_date",
    ]
    list_filter = ["maturity"]


@admin.register(ReviewLog)
class ReviewLogAdmin(OwnedModelAdmin):
    list_display = [
        "reviewed_on",
        "card",
        "quality",
        "composite_score",
        "interval_before",
        "interval_after",
        "maturity_after",
    ]
    readonly_fields = [f.name for f in ReviewLog._meta.fields]
