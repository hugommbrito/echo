from django.urls import path

from apps.accounts.views import CSRFView, LoginView, LogoutView, MeView

urlpatterns = [
    path("auth/csrf/", CSRFView.as_view(), name="auth-csrf"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="me"),
]
