from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import AllowedEmailDomain, Profile, User

MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_AVATAR_DIMENSION = 4096         # pixels, width or height
ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    full_name = serializers.CharField(max_length=150)

    def validate_email(self, value):
        email = value.strip().lower()
        domain = email.rsplit("@", 1)[-1]
        if not AllowedEmailDomain.objects.filter(domain=domain, is_active=True).exists():
            raise serializers.ValidationError(
                "Please use your college email address."
            )
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )
        return email

    def validate(self, attrs):
        candidate = User(email=attrs["email"])
        try:
            validate_password(attrs["password"], user=candidate)
        except Exception as exc:
            messages = getattr(exc, "messages", [str(exc)])
            raise serializers.ValidationError({"password": messages})
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
        )
        user.profile.full_name = validated_data["full_name"]
        user.profile.save(update_fields=["full_name", "updated_at"])
        return user


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField()


class LoginSerializer(TokenObtainPairSerializer):
    """Email + password login that only works for verified accounts."""

    def validate(self, attrs):
        field = self.username_field  # "email" for our custom User
        attrs[field] = attrs[field].strip().lower()
        data = super().validate(attrs)
        if not self.user.is_email_verified:
            raise PermissionDenied(
                "Please verify your college email before logging in."
            )
        return data


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["full_name", "college_name", "phone", "bio", "avatar"]

    def validate_avatar(self, value):
        if value is None:  # JSON {"avatar": null} clears the avatar
            return value
        if value.size > MAX_AVATAR_BYTES:
            raise serializers.ValidationError("Image must be 2 MB or smaller.")
        if getattr(value, "content_type", None) not in ALLOWED_AVATAR_TYPES:
            raise serializers.ValidationError("Use a JPEG, PNG or WebP image.")
        width, height = value.image.size
        if max(width, height) > MAX_AVATAR_DIMENSION:
            raise serializers.ValidationError("Image dimensions are too large.")
        return value


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "is_email_verified", "profile"]
        read_only_fields = fields
