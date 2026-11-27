from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import ContactRequestViewSet, ReportCreateView

router = SimpleRouter()
router.register("requests", ContactRequestViewSet, basename="contact-request")

urlpatterns = [
    path("reports/", ReportCreateView.as_view(), name="report-create"),
] + router.urls