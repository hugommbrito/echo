from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.accounts.views import (
    CSRFView,
    LanguageCatalogView,
    LanguageProfileViewSet,
    LoginView,
    LogoutView,
    MeAIUsageView,
    MeView,
)

router = DefaultRouter(trailing_slash=True)
router.register("me/languages", LanguageProfileViewSet, basename="me-language")

urlpatterns = [
    path("auth/csrf/", CSRFView.as_view(), name="auth-csrf"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="me"),
    path("me/ai-usage/", MeAIUsageView.as_view(), name="me-ai-usage"),
    path("languages/", LanguageCatalogView.as_view(), name="languages"),
    *router.urls,
]
