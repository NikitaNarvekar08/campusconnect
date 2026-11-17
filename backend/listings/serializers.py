from decimal import Decimal

from rest_framework import serializers

from accounts.models import Campus

from .image_utils import sanitize_image, validate_image_upload
from .models import Category, Listing


class ListingSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(
        slug_field="slug", queryset=Category.objects.all()
    )
    category_name = serializers.CharField(source="category.name", read_only=True)
    campus = serializers.CharField(source="campus.name", read_only=True)
    seller = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = (
            "id",
            "title",
            "description",
            "price",
            "condition",
            "status",
            "image",
            "category",
            "category_name",
            "campus",
            "seller",
            "is_owner",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        extra_kwargs = {"price": {"min_value": Decimal("0")}}

    def get_seller(self, obj):
        # only what a buyer needs: never the seller's email or phone
        return {"id": obj.seller_id, "full_name": obj.seller.profile.full_name}

    def get_is_owner(self, obj):
        request = self.context.get("request")
        return bool(
            request and request.user.is_authenticated and obj.seller_id == request.user.id
        )

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug")


class CampusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campus
        fields = ("id", "name", "city")


class ListingImageSerializer(serializers.Serializer):
    image = serializers.ImageField(validators=[validate_image_upload])

    def validate_image(self, file):
        return sanitize_image(file)