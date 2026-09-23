from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import services
from apps.accounts.models import LanguageProfile
from apps.accounts.scoping import OwnedQuerySetMixin
from apps.accounts.serializers import (
    LanguageActivateSerializer,
    LanguageCatalogSerializer,
    LanguageProfileSerializer,
    LoginSerializer,
    UserSerializer,
)
from apps.core.languages import LANGUAGES


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CSRFView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=inline_serializer("CSRFToken", {"csrfToken": serializers.CharField()}))
    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class InvalidCredentials(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Invalid e-mail or password."
    default_code = "invalid_credentials"


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=LoginSerializer, responses=UserSerializer)
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request._request,
            username=serializer.validated_data["email"].lower(),
            password=serializer.validated_data["password"],
        )
        if user is None:
            raise InvalidCredentials()
        login(request._request, user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    @extend_schema(request=UserSerializer, responses=UserSerializer)
    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class LanguageCatalogView(APIView):
    """Languages the app supports (activated or not)."""

    @extend_schema(responses=LanguageCatalogSerializer(many=True))
    def get(self, request):
        rows = [
            {
                "code": spec.code,
                "name": spec.name_pt,
                "name_en": spec.name_en,
                "starting_levels": list(settings.ECHO_SELF_PLACEMENT_LEVELS),
            }
            for spec in LANGUAGES.values()
        ]
        return Response(LanguageCatalogSerializer(rows, many=True).data)


class LanguageProfileViewSet(
    OwnedQuerySetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """The learner's practised languages: activate (POST), pause/resume and daily target (PATCH)."""

    model = LanguageProfile
    serializer_class = LanguageProfileSerializer
    lookup_field = "language"
    lookup_value_regex = r"[a-z]{2}"
    http_method_names = ["get", "post", "patch", "head", "options"]
    pagination_class = None

    def get_base_queryset(self):
        return LanguageProfile.objects.order_by("language")

    @extend_schema(request=LanguageActivateSerializer, responses={201: LanguageProfileSerializer})
    def create(self, request, *args, **kwargs):
        serializer = LanguageActivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = services.activate_language(
            request.user,
            language=serializer.validated_data["language"],
            starting_level=serializer.validated_data.get("starting_level"),
        )
        return Response(LanguageProfileSerializer(profile).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        services.update_language_profile(
            serializer.instance,
            is_active=serializer.validated_data.get("is_active"),
            default_new_cards_per_day=serializer.validated_data.get("default_new_cards_per_day"),
        )
