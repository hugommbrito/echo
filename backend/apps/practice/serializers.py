from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.cards.serializers import CardSerializer, CategoryBriefSerializer
from apps.core.languages import LanguageCode
from apps.leveling.elo import band_for_rating
from apps.leveling.serializers import LevelLogSerializer
from apps.practice import queue
from apps.practice.models import Attempt, DailySession, Evaluation, SessionLanguagePlan
from apps.scheduling.serializers import ReviewLogSerializer


class SessionCreateSerializer(serializers.Serializer):
    category_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=True)
    new_cards_targets = serializers.DictField(
        child=serializers.IntegerField(min_value=0, max_value=settings.ECHO_MAX_NEW_CARDS_PER_DAY),
        help_text='New cards per active language, e.g. {"en": 3, "fr": 2}',
    )


class LanguageProjectionSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=LanguageCode.choices)
    base_level = serializers.CharField()
    carried_over = serializers.IntegerField()
    available_carry_over = serializers.IntegerField()
    to_generate = serializers.IntegerField()
    probes = serializers.IntegerField()
    due_today = serializers.IntegerField()
    overdue = serializers.IntegerField()
    total = serializers.IntegerField()


class ProjectionSerializer(serializers.Serializer):
    languages = LanguageProjectionSerializer(many=True)
    carried_over = serializers.IntegerField()
    to_generate = serializers.IntegerField()
    due_today = serializers.IntegerField()
    overdue = serializers.IntegerField()
    probes = serializers.IntegerField()
    total = serializers.IntegerField()


class ProgressSerializer(serializers.Serializer):
    new_total = serializers.IntegerField()
    new_done = serializers.IntegerField()
    due_total = serializers.IntegerField()
    due_done = serializers.IntegerField()
    remaining = serializers.IntegerField()


class SessionLanguagePlanSerializer(serializers.ModelSerializer):
    base_level = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    class Meta:
        model = SessionLanguagePlan
        fields = [
            "language",
            "new_cards_target",
            "rating_at_start",
            "base_level",
            "generation_status",
            "generation_error",
            "generated_count",
            "progress",
        ]
        read_only_fields = fields

    def get_base_level(self, plan: SessionLanguagePlan) -> str:
        return band_for_rating(plan.rating_at_start)

    @extend_schema_field(ProgressSerializer)
    def get_progress(self, plan: SessionLanguagePlan) -> dict:
        return ProgressSerializer(queue.progress(plan.session, plan.language)).data


class DailySessionSerializer(serializers.ModelSerializer):
    categories = CategoryBriefSerializer(many=True, read_only=True)
    new_cards_target = serializers.IntegerField(source="new_cards_target_total", read_only=True)
    plans = SessionLanguagePlanSerializer(many=True, read_only=True)
    progress = serializers.SerializerMethodField()
    projected = serializers.SerializerMethodField()

    class Meta:
        model = DailySession
        fields = [
            "id",
            "session_date",
            "new_cards_target",
            "categories",
            "status",
            "generation_error",
            "completed_at",
            "created_at",
            "plans",
            "progress",
            "projected",
        ]
        read_only_fields = fields

    @extend_schema_field(ProgressSerializer)
    def get_progress(self, session: DailySession) -> dict:
        return ProgressSerializer(queue.progress(session)).data

    @extend_schema_field(ProjectionSerializer(allow_null=True))
    def get_projected(self, session: DailySession) -> dict | None:
        projection = self.context.get("projection")
        return ProjectionSerializer(projection.as_dict()).data if projection is not None else None


class QueueItemSerializer(serializers.Serializer):
    kind = serializers.CharField()
    position = serializers.IntegerField(allow_null=True)
    origin = serializers.CharField(allow_null=True)
    due_date = serializers.DateField(allow_null=True)
    card = CardSerializer()


class DimensionSerializer(serializers.Serializer):
    score = serializers.IntegerField()
    feedback = serializers.CharField()


class GrammarDimensionSerializer(DimensionSerializer):
    issues = serializers.ListField(child=serializers.DictField())


class FluencyDimensionSerializer(DimensionSerializer):
    markers = serializers.DictField()


class EvaluationSerializer(serializers.Serializer):
    structure = serializers.SerializerMethodField()
    grammar = serializers.SerializerMethodField()
    fluency = serializers.SerializerMethodField()
    composite_score = serializers.DecimalField(max_digits=3, decimal_places=2)
    sm2_quality = serializers.IntegerField()
    key_points = serializers.SerializerMethodField()
    improved_answer = serializers.CharField(allow_null=True)
    improved_answer_notes = serializers.ListField(child=serializers.CharField())
    model = serializers.CharField()

    def get_structure(self, ev: Evaluation) -> dict:
        return {"score": ev.structure_score, "feedback": ev.structure_feedback}

    def get_grammar(self, ev: Evaluation) -> dict:
        return {
            "score": ev.grammar_score,
            "feedback": ev.grammar_feedback,
            "issues": ev.grammar_issues or [],
        }

    def get_fluency(self, ev: Evaluation) -> dict:
        return {
            "score": ev.fluency_score,
            "feedback": ev.fluency_feedback,
            "markers": ev.fluency_markers or {},
        }

    def get_key_points(self, ev: Evaluation) -> list[str]:
        return list(ev.attempt.card.key_points or [])


class AttemptSerializer(serializers.ModelSerializer):
    card_id = serializers.UUIDField(read_only=True)
    language = serializers.CharField(source="card.language", read_only=True)
    session_id = serializers.UUIDField(read_only=True, allow_null=True)
    audio_url = serializers.SerializerMethodField()
    evaluation = serializers.SerializerMethodField()
    review = serializers.SerializerMethodField()
    level_change = serializers.SerializerMethodField()

    class Meta:
        model = Attempt
        fields = [
            "id",
            "status",
            "failure_stage",
            "error_message",
            "card_id",
            "language",
            "session_id",
            "attempt_number",
            "attempted_on",
            "counts_for_scheduling",
            "insufficient_speech",
            "audio_url",
            "audio_mime",
            "audio_duration_seconds",
            "transcript_text",
            "word_count",
            "words_per_minute",
            "transcription_model",
            "evaluation",
            "review",
            "level_change",
            "created_at",
            "completed_at",
        ]
        read_only_fields = fields

    def get_audio_url(self, attempt: Attempt) -> str | None:
        try:
            return attempt.audio_file.url if attempt.audio_file else None
        except (ValueError, NotImplementedError):
            return None

    def get_evaluation(self, attempt: Attempt) -> dict | None:
        evaluation = getattr(attempt, "evaluation", None)
        return EvaluationSerializer(evaluation).data if evaluation is not None else None

    def get_review(self, attempt: Attempt) -> dict | None:
        review = getattr(attempt, "review", None)
        return ReviewLogSerializer(review).data if review is not None else None

    def get_level_change(self, attempt: Attempt) -> dict | None:
        change = getattr(attempt, "level_change", None)
        return LevelLogSerializer(change).data if change is not None else None


class AttemptHistorySerializer(AttemptSerializer):
    pass


class AttemptCreateSerializer(serializers.Serializer):
    card_id = serializers.UUIDField()
    session_id = serializers.UUIDField(required=False, allow_null=True)
    audio = serializers.FileField()
    duration_seconds = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False, allow_null=True
    )
    mime_type = serializers.CharField(required=False, allow_blank=True)


class AttemptAcceptedSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()


class ImprovedAnswerSerializer(serializers.Serializer):
    improved_answer = serializers.CharField()
    notes = serializers.ListField(child=serializers.CharField())
    model = serializers.CharField()
    generated_at = serializers.DateTimeField()
