from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import CampusListView, CategoryListView, ListingViewSet

router = SimpleRouter()
router.register("listings", ListingViewSet, basename="listing")

urlpatterns = [
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("campuses/", CampusListView.as_view(), name="campus-list"),
] + router.urls