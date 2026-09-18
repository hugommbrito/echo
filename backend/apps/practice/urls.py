from rest_framework.routers import DefaultRouter

from apps.practice.views import AttemptViewSet, SessionViewSet

router = DefaultRouter(trailing_slash=True)
router.register("sessions", SessionViewSet, basename="session")
router.register("attempts", AttemptViewSet, basename="attempt")

urlpatterns = router.urls
