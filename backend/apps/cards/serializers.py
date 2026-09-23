from __future__ import annotations

from rest_framework import serializers

from apps.cards.models import Card, Category


class CategorySerializer(serializers.ModelSerializer):
    scope = serializers.CharField(read_only=True)
    card_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Category
        fields = [
            "id",
            "slug",
            "name",
            "description",
            "generation_hint",
            "is_active",
            "sort_order",
            "scope",
            "card_count",
        ]
        read_only_fields = ["id", "scope", "card_count"]

    def validate_slug(self, value: str) -> str:
        user = self.context["request"].user
        qs = Category.objects.visible_to(user).filter(slug=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A category with this slug already exists.", code="slug_taken"
            )
        return value


class CategoryBriefSerializer(serializers.ModelSerializer):
    scope = serializers.CharField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "slug", "name", "scope"]


class CardSerializer(serializers.ModelSerializer):
    category = CategoryBriefSerializer(read_only=True)
    maturity = serializers.SerializerMethodField()
    attempt_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Card
        fields = [
            "id",
            "language",
            "category",
            "question_text",
            "scenario",
            "key_points",
            "cefr_level",
            "difficulty_rating",
            "probe",
            "status",
            "source",
            "maturity",
            "attempt_count",
            "created_at",
        ]
        read_only_fields = fields

    def get_maturity(self, card: Card) -> str:
        scheduler = getattr(card, "scheduler", None)
        return scheduler.maturity if scheduler is not None else "new"


class CardDetailSerializer(CardSerializer):
    scheduler = serializers.SerializerMethodField()
    last_scores = serializers.SerializerMethodField()

    class Meta(CardSerializer.Meta):
        fields = CardSerializer.Meta.fields + ["scheduler", "last_scores"]
        read_only_fields = fields

    def get_scheduler(self, card: Card) -> dict | None:
        from apps.scheduling.serializers import SchedulerStateSerializer

        scheduler = getattr(card, "scheduler", None)
        return SchedulerStateSerializer(scheduler).data if scheduler is not None else None

    def get_last_scores(self, card: Card) -> dict | None:
        from apps.practice.models import Attempt, AttemptStatus

        attempt = (
            Attempt.objects.filter(card=card, status=AttemptStatus.COMPLETED)
            .select_related("evaluation")
            .order_by("-attempt_number")
            .first()
        )
        if attempt is None or not hasattr(attempt, "evaluation"):
            return None
        ev = attempt.evaluation
        return {
            "attempt_id": str(attempt.id),
            "attempted_on": attempt.attempted_on,
            "structure": ev.structure_score,
            "grammar": ev.grammar_score,
            "fluency": ev.fluency_score,
            "composite": str(ev.composite_score),
        }
