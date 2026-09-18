from rest_framework.routers import DefaultRouter

from apps.cards.views import CardViewSet, CategoryViewSet

router = DefaultRouter(trailing_slash=True)
router.register("categories", CategoryViewSet, basename="category")
router.register("cards", CardViewSet, basename="card")

urlpatterns = router.urls
