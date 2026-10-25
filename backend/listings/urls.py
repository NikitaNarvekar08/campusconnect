from rest_framework.routers import SimpleRouter

from .views import CategoryViewSet, ListingViewSet

router = SimpleRouter()
router.register("listings", ListingViewSet, basename="listing")
router.register("categories", CategoryViewSet, basename="category")

urlpatterns = router.urls
