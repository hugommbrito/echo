import contextlib

from django.contrib import admin
from django.db.models import Sum

from apps.ai.models import AIRequestLog, KeySource
from apps.core.admin import OwnedModelAdmin


@admin.register(AIRequestLog)
class AIRequestLogAdmin(OwnedModelAdmin):
    list_display = [
        "created_at",
        "kind",
        "language",
        "provider",
        "key_source",
        "model",
        "input_tokens",
        "output_tokens",
        "audio_seconds",
        "estimated_cost_usd",
        "latency_ms",
        "status",
    ]
    list_filter = ["kind", "key_source", "language", "provider", "model", "status", "created_at"]
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in AIRequestLog._meta.fields]

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        qs = self.get_queryset(request)
        with contextlib.suppress(Exception):  # fall back to the unfiltered set
            qs = self.get_changelist_instance(request).get_queryset(request)
        extra_context["total_cost_usd"] = (
            qs.aggregate(total=Sum("estimated_cost_usd"))["total"] or 0
        )
        by_source = {
            row["key_source"]: row["total"] or 0
            for row in qs.values("key_source").annotate(total=Sum("estimated_cost_usd"))
        }
        extra_context["cost_global_usd"] = by_source.get(KeySource.GLOBAL, 0)
        extra_context["cost_user_usd"] = by_source.get(KeySource.USER, 0)
        return super().changelist_view(request, extra_context=extra_context)
