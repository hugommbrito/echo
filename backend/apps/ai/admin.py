from django.contrib import admin
from django.db.models import Sum

from apps.ai.models import AIRequestLog
from apps.core.admin import OwnedModelAdmin


@admin.register(AIRequestLog)
class AIRequestLogAdmin(OwnedModelAdmin):
    list_display = [
        "created_at",
        "kind",
        "language",
        "provider",
        "model",
        "input_tokens",
        "output_tokens",
        "audio_seconds",
        "estimated_cost_usd",
        "latency_ms",
        "status",
    ]
    list_filter = ["kind", "language", "provider", "model", "status", "created_at"]
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in AIRequestLog._meta.fields]

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        qs = self.get_queryset(request)
        extra_context["total_cost_usd"] = (
            qs.aggregate(total=Sum("estimated_cost_usd"))["total"] or 0
        )
        return super().changelist_view(request, extra_context=extra_context)
