from rest_framework.routers import SimpleRouter

from .views import ContactRequestViewSet

router = SimpleRouter()
router.register("requests", ContactRequestViewSet, basename="contact-request")

urlpatterns = router.urls