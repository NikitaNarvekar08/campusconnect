from rest_framework import serializers

from listings.models import Listing
from listings.serializers import ListingSerializer

from .models import Wishlist


class WishlistSerializer(serializers.ModelSerializer):
    listing = ListingSerializer(read_only=True)

    class Meta:
        model = Wishlist
        fields = ["id", "listing", "created_at"]


class AddToWishlistSerializer(serializers.Serializer):
    # Removed listings are not in this queryset, so they can't be saved.
    listing = serializers.PrimaryKeyRelatedField(
        queryset=Listing.objects.exclude(status=Listing.Status.REMOVED)
    )

    def validate_listing(self, listing):
        if listing.seller_id == self.context["request"].user.id:
            raise serializers.ValidationError("You cannot save your own listing.")
        return listing
