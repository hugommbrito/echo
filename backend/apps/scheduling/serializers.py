from rest_framework import serializers

from apps.scheduling.models import ReviewLog, SchedulerState


class SchedulerStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchedulerState
        fields = [
            "maturity",
            "ease_factor",
            "interval_days",
            "repetitions",
            "lapses",
            "total_reviews",
            "due_date",
            "last_reviewed_on",
            "last_quality",
        ]


class ReviewLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewLog
        fields = [
            "quality",
            "composite_score",
            "ease_before",
            "ease_after",
            "interval_before",
            "interval_after",
            "due_before",
            "due_after",
            "maturity_before",
            "maturity_after",
            "reviewed_on",
        ]
