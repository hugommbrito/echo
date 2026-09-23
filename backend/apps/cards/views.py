from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.accounts.scoping import OwnedQuerySetMixin
from apps.cards.models import Card, CardStatus, Category
from apps.cards.serializers import CardDetailSerializer, CardSerializer, CategorySerializer
from apps.core.languages import language_codes


@extend_schema(parameters=[OpenApiParameter("active", bool, description="Only active categories")])
class CategoryViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Global categories (read-only) plus the user's personal ones."""

    serializer_class = CategorySerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Category.objects.none()
        user = self.request.user
        qs = Category.objects.visible_to(user).annotate(
            card_count=Count("cards", filter=Q(cards__user=user))
        )
        active = self.request.query_params.get("active")
        if active is not None and active.lower() in {"1", "true", "yes"}:
            qs = qs.filter(is_active=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.owner_id != self.request.user.pk:
            raise PermissionDenied("Global categories can only be edited by an admin.")
        serializer.save()


@extend_schema(
    parameters=[
        OpenApiParameter("language", str, enum=language_codes()),
        OpenApiParameter("category", str, description="Category id or slug"),
        OpenApiParameter("maturity", str, enum=["new", "learning", "mature"]),
        OpenApiParameter("level", str, enum=["A1", "A2", "B1", "B2", "C1", "C2"]),
        OpenApiParameter("status", str, enum=["active", "suspended", "archived"]),
        OpenApiParameter("q", str, description="Search in the question text"),
    ]
)
class CardViewSet(OwnedQuerySetMixin, viewsets.ReadOnlyModelViewSet):
    model = Card
    serializer_class = CardSerializer

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CardDetailSerializer
        return CardSerializer

    def get_base_queryset(self):
        return (
            Card.objects.select_related("category", "scheduler")
            .annotate(attempt_count=Count("attempts", filter=Q(attempts__status="completed")))
            .order_by("-created_at")
        )

    def filter_queryset(self, queryset):
        params = self.request.query_params
        if language := params.get("language"):
            queryset = queryset.filter(language=language)
        if category := params.get("category"):
            queryset = (
                queryset.filter(Q(category__slug=category) | Q(category_id=category))
                if _is_uuid(category)
                else queryset.filter(category__slug=category)
            )
        if maturity := params.get("maturity"):
            queryset = queryset.filter(scheduler__maturity=maturity)
        if level := params.get("level"):
            queryset = queryset.filter(cefr_level=level)
        if status_ := params.get("status"):
            queryset = queryset.filter(status=status_)
        if q := params.get("q"):
            queryset = queryset.filter(question_text__icontains=q)
        return queryset

    @extend_schema(request=None, responses=CardDetailSerializer)
    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        card = self.get_object()
        card.status = CardStatus.SUSPENDED
        card.save(update_fields=["status", "updated_at"])
        return Response(CardDetailSerializer(card, context={"request": request}).data)

    @extend_schema(request=None, responses=CardDetailSerializer)
    @action(detail=True, methods=["post"])
    def unsuspend(self, request, pk=None):
        card = self.get_object()
        card.status = CardStatus.ACTIVE
        card.save(update_fields=["status", "updated_at"])
        return Response(CardDetailSerializer(card, context={"request": request}).data)

    @extend_schema(responses=None)
    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        from apps.practice.serializers import AttemptHistorySerializer
        from apps.practice.services import card_history

        card = self.get_object()
        attempts = card_history(card)
        return Response(
            AttemptHistorySerializer(attempts, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


def _is_uuid(value: str) -> bool:
    import uuid

    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError):
        return False
