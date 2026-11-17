from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    CampusListView,
    CategoryListView,
    ListingViewSet,
    WishlistRemoveView,
    WishlistView,
)

router = SimpleRouter()
router.register("listings", ListingViewSet, basename="listing")

urlpatterns = [
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("campuses/", CampusListView.as_view(), name="campus-list"),
    path("wishlist/", WishlistView.as_view(), name="wishlist"),
    path("wishlist/<int:listing_id>/", WishlistRemoveView.as_view(), name="wishlist-remove"),
] + router.urls