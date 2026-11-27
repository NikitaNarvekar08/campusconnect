from django.db import IntegrityError, transaction
from rest_framework import serializers

from listings.models import Listing

from .models import ContactRequest, Report

ALREADY_CONTACTED = "You have already contacted the seller about this listing."
ALREADY_REPORTED = "You have already reported this listing."


class ContactRequestCreateSerializer(serializers.Serializer):
    listing = serializers.IntegerField(min_value=1)
    message = serializers.CharField(max_length=500)

    def validate(self, attrs):
        user = self.context["request"].user
        try:
            listing = Listing.objects.get(pk=attrs["listing"], is_hidden=False)
        except Listing.DoesNotExist:
            raise serializers.ValidationError({"listing": ["Listing not found."]})

        if listing.seller_id == user.id:
            raise serializers.ValidationError(
                {"listing": ["You can't contact yourself about your own listing."]}
            )
        if listing.status != Listing.Status.AVAILABLE:
            raise serializers.ValidationError(
                {"listing": ["This listing is no longer available."]}
            )
        if ContactRequest.objects.filter(listing=listing, requester=user).exists():
            raise serializers.ValidationError({"listing": [ALREADY_CONTACTED]})

        attrs["listing"] = listing
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return ContactRequest.objects.create(
                    requester=self.context["request"].user,
                    listing=validated_data["listing"],
                    message=validated_data["message"],
                )
        except IntegrityError:
            # two identical requests at the same moment: the unique constraint caught the second
            raise serializers.ValidationError({"listing": [ALREADY_CONTACTED]})


class ContactRequestSerializer(serializers.ModelSerializer):
    listing = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    other_party = serializers.SerializerMethodField()

    class Meta:
        model = ContactRequest
        fields = (
            "id",
            "listing",
            "message",
            "status",
            "role",
            "other_party",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def _is_sender(self, obj):
        return obj.requester_id == self.context["request"].user.id

    def get_listing(self, obj):
        listing = obj.listing
        return {
            "id": listing.id,
            "title": listing.title,
            "price": f"{listing.price:.2f}",
            "status": listing.status,
        }

    def get_role(self, obj):
        return "sent" if self._is_sender(obj) else "received"

    def get_other_party(self, obj):
        other = obj.listing.seller if self._is_sender(obj) else obj.requester
        profile = other.profile
        data = {
            "id": other.id,
            "full_name": profile.full_name,
            "campus": profile.campus.name if profile.campus else None,
        }
        # contact details are shared only after the seller accepts, and only with the two people involved
        if obj.status == ContactRequest.Status.ACCEPTED:
            data["email"] = other.email
            data["phone"] = profile.phone or None
        return data


class ReportCreateSerializer(serializers.Serializer):
    listing = serializers.IntegerField(min_value=1)
    reason = serializers.ChoiceField(choices=Report.Reason.choices)
    details = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default=""
    )

    def validate(self, attrs):
        user = self.context["request"].user
        try:
            listing = Listing.objects.get(pk=attrs["listing"], is_hidden=False)
        except Listing.DoesNotExist:
            raise serializers.ValidationError({"listing": ["Listing not found."]})

        if listing.seller_id == user.id:
            raise serializers.ValidationError(
                {"listing": ["You can't report your own listing."]}
            )
        if Report.objects.filter(listing=listing, reporter=user).exists():
            raise serializers.ValidationError({"listing": [ALREADY_REPORTED]})
        if attrs["reason"] == Report.Reason.OTHER and not attrs["details"].strip():
            raise serializers.ValidationError({"details": ["Please describe the problem."]})

        attrs["listing"] = listing
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return Report.objects.create(
                    listing=validated_data["listing"],
                    reporter=self.context["request"].user,
                    reason=validated_data["reason"],
                    details=validated_data["details"].strip(),
                )
        except IntegrityError:
            raise serializers.ValidationError({"listing": [ALREADY_REPORTED]})


class ReportSerializer(serializers.ModelSerializer):
    """What the reporter gets back: nothing about other reporters or the moderation."""

    class Meta:
        model = Report
        fields = ("id", "listing", "reason", "status", "created_at")
        read_only_fields = fields