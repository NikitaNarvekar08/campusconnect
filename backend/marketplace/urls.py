from django.urls import path
from rest_framework.routers import SimpleRouter

from .dashboard import DashboardView
from .views import ContactRequestViewSet, ReportCreateView

router = SimpleRouter()
router.register("requests", ContactRequestViewSet, basename="contact-request")

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("reports/", ReportCreateView.as_view(), name="report-create"),
] + router.urls