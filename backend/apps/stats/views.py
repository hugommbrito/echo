from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.stats import queries

PERIOD_PARAMS = [
    OpenApiParameter(
        "from", str, description="Start date (YYYY-MM-DD), default: 29 days before `to`"
    ),
    OpenApiParameter(
        "to", str, description="End date (YYYY-MM-DD), default: today in the user's timezone"
    ),
    OpenApiParameter("category", str, description="Category id or slug"),
]


class StatsView(APIView):
    """Base for dashboard endpoints. All querysets are scoped by the fail-closed manager."""

    def period(self):
        try:
            return queries.parse_period(
                self.request.user,
                self.request.query_params.get("from"),
                self.request.query_params.get("to"),
            )
        except ValueError:
            raise ValidationError({"from": ["Dates must be YYYY-MM-DD."]}, code="invalid_date")

    def category(self):
        raw = self.request.query_params.get("category")
        category = queries.resolve_category(self.request.user, raw)
        if raw and category is None:
            raise ValidationError({"category": ["Unknown category."]}, code="unknown_category")
        return category

    def bucket(self) -> str:
        bucket = self.request.query_params.get("bucket", "day")
        if bucket not in {"day", "week"}:
            raise ValidationError({"bucket": ["Must be 'day' or 'week'."]}, code="invalid_bucket")
        return bucket

    def int_param(self, name: str, default: int, lo: int, hi: int) -> int:
        raw = self.request.query_params.get(name)
        if raw is None:
            return default
        try:
            value = int(raw)
        except ValueError:
            raise ValidationError({name: ["Must be an integer."]})
        return max(lo, min(hi, value))


@extend_schema(parameters=PERIOD_PARAMS, responses=OpenApiTypes.OBJECT)
class OverviewView(StatsView):
    def get(self, request):
        return Response(queries.overview(request.user, self.period(), self.category()))


@extend_schema(
    parameters=PERIOD_PARAMS + [OpenApiParameter("bucket", str, enum=["day", "week"])],
    responses=OpenApiTypes.OBJECT,
)
class ScoresView(StatsView):
    def get(self, request):
        return Response(queries.scores(self.period(), self.category(), self.bucket()))


@extend_schema(parameters=PERIOD_PARAMS, responses=OpenApiTypes.OBJECT)
class LevelView(StatsView):
    def get(self, request):
        return Response(queries.level(request.user, self.period()))


@extend_schema(
    parameters=PERIOD_PARAMS + [OpenApiParameter("bucket", str, enum=["day", "week"])],
    responses=OpenApiTypes.OBJECT,
)
class ActivityView(StatsView):
    def get(self, request):
        return Response(queries.activity(self.period(), self.category(), self.bucket()))


@extend_schema(parameters=[OpenApiParameter("days", int)], responses=OpenApiTypes.OBJECT)
class ForecastView(StatsView):
    def get(self, request):
        return Response(queries.forecast(request.user, self.int_param("days", 30, 1, 365)))


@extend_schema(responses=OpenApiTypes.OBJECT)
class CollectionView(StatsView):
    def get(self, request):
        return Response(queries.collection(request.user))


@extend_schema(parameters=PERIOD_PARAMS, responses=OpenApiTypes.OBJECT)
class GrammarIssuesView(StatsView):
    def get(self, request):
        return Response(queries.grammar_issues(self.period(), self.category()))


@extend_schema(parameters=PERIOD_PARAMS, responses=OpenApiTypes.OBJECT)
class CategoriesView(StatsView):
    def get(self, request):
        return Response(queries.categories(request.user, self.period()))


@extend_schema(
    parameters=[OpenApiParameter("year", int), OpenApiParameter("category", str)],
    responses=OpenApiTypes.OBJECT,
)
class HeatmapView(StatsView):
    def get(self, request):
        year = self.int_param("year", request.user.local_today().year, 2000, 2100)
        return Response(queries.heatmap(request.user, year, self.category()))


@extend_schema(responses=OpenApiTypes.OBJECT)
class AdvancedView(StatsView):
    def get(self, request):
        return Response(queries.advanced(request.user))
