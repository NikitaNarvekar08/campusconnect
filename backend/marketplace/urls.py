from django.urls import path

from .views import WishlistIdsView, WishlistRemoveView, WishlistView

urlpatterns = [
    path("wishlist/", WishlistView.as_view(), name="wishlist"),
    path("wishlist/ids/", WishlistIdsView.as_view(), name="wishlist-ids"),
    path("wishlist/<int:listing_id>/", WishlistRemoveView.as_view(), name="wishlist-remove"),
]
