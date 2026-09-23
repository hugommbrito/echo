from django.contrib import admin

from apps.core.admin import OwnedModelAdmin
from apps.leveling.models import LevelLog


@admin.register(LevelLog)
class LevelLogAdmin(OwnedModelAdmin):
    list_display = [
        "logged_on",
        "language",
        "card",
        "rating_before",
        "rating_after",
        "delta",
        "question_rating",
        "k_factor",
    ]
    list_filter = ["language"]
    readonly_fields = [f.name for f in LevelLog._meta.fields]
