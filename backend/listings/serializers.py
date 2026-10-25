from rest_framework import serializers

from accounts.models import User

from .models import Category, Listing, ListingImage
from .validators import validate_uploaded_image


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class SellerSerializer(serializers.ModelSerializer):
    """Public seller info only: no email, no phone."""

    full_name = serializers.CharField(source="profile.full_name", read_only=True)
    college_name = serializers.CharField(source="profile.college_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "full_name", "college_name"]


class ListingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingImage
        fields = ["id", "image", "position"]
        read_only_fields = ["id", "position"]

    def validate_image(self, value):
        return validate_uploaded_image(value)


class ListingSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(
        slug_field="slug", queryset=Category.objects.all()
    )
    seller = SellerSerializer(read_only=True)
    images = ListingImageSerializer(many=True, read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id", "title", "description", "price", "condition", "status",
            "category", "seller", "images", "is_owner", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_is_owner(self, obj):
        request = self.context.get("request")
        return bool(
            request and request.user.is_authenticated and obj.seller_id == request.user.id
        )

    def validate_status(self, value):
        # Only moderators (via Admin) may set a listing to "removed".
        if value == Listing.Status.REMOVED:
            raise serializers.ValidationError("You cannot set this status.")
        return value

    def validate(self, attrs):
        if self.instance and self.instance.status == Listing.Status.REMOVED:
            raise serializers.ValidationError(
                "This listing was removed by a moderator and cannot be edited."
            )
        return attrs
