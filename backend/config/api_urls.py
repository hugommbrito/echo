from django.urls import include, path

urlpatterns = [
    path("", include("apps.accounts.urls")),
    path("", include("apps.cards.urls")),
    path("", include("apps.practice.urls")),
    path("", include("apps.stats.urls")),
]
