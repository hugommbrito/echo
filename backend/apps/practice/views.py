from django.http import HttpResponseRedirect
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.scoping import OwnedQuerySetMixin
from apps.core.languages import is_known_language, language_codes
from apps.practice import attempts as attempt_services
from apps.practice import queue, services
from apps.practice.improved_answer import get_or_generate_improved_answer
from apps.practice.models import Attempt, DailySession
from apps.practice.serializers import (
    AttemptAcceptedSerializer,
    AttemptCreateSerializer,
    AttemptSerializer,
    DailySessionSerializer,
    ImprovedAnswerSerializer,
    ProjectionSerializer,
    QueueItemSerializer,
    SessionCreateSerializer,
)


class SessionViewSet(
    OwnedQuerySetMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    model = DailySession
    serializer_class = DailySessionSerializer

    def get_base_queryset(self):
        return DailySession.objects.prefetch_related("categories", "plans").order_by(
            "-session_date"
        )

    @extend_schema(parameters=[OpenApiParameter("from", str), OpenApiParameter("to", str)])
    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        if start := request.query_params.get("from"):
            qs = qs.filter(session_date__gte=start)
        if end := request.query_params.get("to"):
            qs = qs.filter(session_date__lte=end)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page if page is not None else qs, many=True)
        return (
            self.get_paginated_response(serializer.data)
            if page is not None
            else Response(serializer.data)
        )

    def retrieve(self, request, *args, **kwargs):
        session = services.refresh_status(self.get_object())
        return Response(self.get_serializer(session).data)

    @extend_schema(request=SessionCreateSerializer, responses={201: DailySessionSerializer})
    def create(self, request, *args, **kwargs):
        serializer = SessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        targets = services.resolve_targets(request.user, data["new_cards_targets"])
        projection = services.project_session(
            request.user, targets=targets, categories=data["category_ids"]
        )
        session = services.create_session(
            request.user, category_ids=data["category_ids"], new_cards_targets=targets
        )
        body = DailySessionSerializer(
            session, context={"request": request, "projection": projection}
        ).data
        return Response(body, status=status.HTTP_201_CREATED)

    @extend_schema(responses=DailySessionSerializer)
    @action(detail=False, methods=["get"])
    def today(self, request):
        session = services.today_session(request.user)
        if session is None:
            raise NotFound("No session for today yet.", code="no_session_today")
        session = services.refresh_status(session)
        return Response(self.get_serializer(session).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "targets",
                str,
                description="New cards per language as lang:count pairs, e.g. en:3,fr:2 "
                "(default: each active language's daily default)",
            ),
            OpenApiParameter("category_ids", str, description="Comma-separated category ids"),
        ],
        responses=ProjectionSerializer,
    )
    @action(detail=False, methods=["get"])
    def projection(self, request):
        raw_targets = services.parse_targets_param(request.query_params.get("targets"))
        if raw_targets is None:
            raw_targets = services.default_targets(request.user)
        targets = services.resolve_targets(request.user, raw_targets) if raw_targets else {}
        raw_ids = [i for i in request.query_params.get("category_ids", "").split(",") if i]
        categories = services.resolve_categories(request.user, raw_ids) if raw_ids else []
        projection = services.project_session(request.user, targets=targets, categories=categories)
        return Response(ProjectionSerializer(projection.as_dict()).data)

    @extend_schema(
        parameters=[
            OpenApiParameter("limit", int),
            OpenApiParameter("language", str, enum=language_codes()),
        ],
        responses=QueueItemSerializer(many=True),
    )
    @action(detail=True, methods=["get"])
    def queue(self, request, pk=None):
        session = services.refresh_status(self.get_object())
        language = request.query_params.get("language") or None
        if language is not None and not is_known_language(language):
            raise ValidationError({"language": ["Unknown language."]}, code="unknown_language")
        items = queue.build_queue(session, language)
        if limit := request.query_params.get("limit"):
            try:
                items = items[: max(0, int(limit))]
            except ValueError:
                raise ValidationError({"limit": ["Must be an integer."]})
        return Response(QueueItemSerializer(items, many=True, context={"request": request}).data)

    @extend_schema(request=None, responses=DailySessionSerializer)
    @action(detail=True, methods=["post"], url_path="retry-generation")
    def retry_generation(self, request, pk=None):
        session = services.retry_generation(self.get_object())
        return Response(self.get_serializer(session).data)

    @extend_schema(request=None, responses=DailySessionSerializer)
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        session = services.complete_session(self.get_object())
        return Response(self.get_serializer(session).data)


class AttemptViewSet(
    OwnedQuerySetMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    model = Attempt
    serializer_class = AttemptSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_base_queryset(self):
        return Attempt.objects.select_related(
            "card",
            "card__category",
            "card__scheduler",
            "session",
            "evaluation",
            "review",
            "level_change",
        )

    @extend_schema(request=AttemptCreateSerializer, responses={202: AttemptAcceptedSerializer})
    def create(self, request, *args, **kwargs):
        serializer = AttemptCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        attempt = attempt_services.create_attempt(
            request.user,
            card_id=data["card_id"],
            session_id=data.get("session_id"),
            audio=data["audio"],
            mime_type=data.get("mime_type"),
            client_duration=data.get("duration_seconds"),
        )
        return Response(
            {"id": str(attempt.id), "status": attempt.status}, status=status.HTTP_202_ACCEPTED
        )

    @extend_schema(request=None, responses=ImprovedAnswerSerializer)
    @action(detail=True, methods=["post"], url_path="improved-answer")
    def improved_answer(self, request, pk=None):
        evaluation = get_or_generate_improved_answer(self.get_object())
        return Response(
            ImprovedAnswerSerializer(
                {
                    "improved_answer": evaluation.improved_answer,
                    "notes": evaluation.improved_answer_notes,
                    "model": evaluation.improved_answer_model,
                    "generated_at": evaluation.improved_answer_generated_at,
                }
            ).data
        )

    @extend_schema(request=None, responses=AttemptSerializer)
    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        attempt = attempt_services.retry_attempt(self.get_object())
        attempt = self.get_queryset().get(pk=attempt.pk)
        return Response(self.get_serializer(attempt).data)

    @extend_schema(responses={302: None})
    @action(detail=True, methods=["get"])
    def audio(self, request, pk=None):
        attempt = self.get_object()
        if not attempt.audio_file:
            raise NotFound("No audio for this attempt.", code="no_audio")
        return HttpResponseRedirect(attempt.audio_file.url)
