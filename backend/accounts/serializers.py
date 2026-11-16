import re
from django.core import signing

from .emails import read_verification_token
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from .models import AllowedEmailDomain, Profile
User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": ["Passwords do not match."]})

        email = attrs["email"].strip().lower()
        domain = email.rsplit("@", 1)[-1]

        allowed = (
            AllowedEmailDomain.objects.select_related("campus")
            .filter(domain=domain, is_active=True)
            .first()
        )
        if allowed is None:
            raise serializers.ValidationError(
                {"email": ["Please register with your college email address."]}
            )

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
                {"email": ["An account with this email already exists."]}
            )

        try:
            validate_password(attrs["password"], user=User(email=email))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})

        attrs["email"] = email
        attrs["campus"] = allowed.campus
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=validated_data["email"],
                    password=validated_data["password"],
                )
                profile = user.profile  # created by the post_save signal
                profile.full_name = validated_data["full_name"]
                profile.campus = validated_data["campus"]
                profile.save(update_fields=["full_name", "campus", "updated_at"])
        except IntegrityError:
            # two requests registered the same email at the same moment
            raise serializers.ValidationError(
                {"email": ["An account with this email already exists."]}
            )
        return user


class CurrentUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="profile.full_name", read_only=True)
    phone = serializers.CharField(source="profile.phone", read_only=True)
    campus = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone",
            "campus",
            "is_email_verified",
            "date_joined",
        )
        read_only_fields = fields

    def get_campus(self, obj):
        campus = obj.profile.campus
        return {"id": campus.id, "name": campus.name} if campus else None


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def save(self, **kwargs):
        request = self.context["request"]
        try:
            token = RefreshToken(self.validated_data["refresh"])
            if str(token["user_id"]) != str(request.user.id):
                raise TokenError("Token does not belong to this user.")
            token.blacklist()
        except TokenError:
            raise serializers.ValidationError({"refresh": ["Invalid or expired token."]})
class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate(self, attrs):
        try:
            payload = read_verification_token(attrs["token"])
        except signing.SignatureExpired:
            raise serializers.ValidationError(
                {"token": ["This verification link has expired. Please request a new one."]}
            )
        except signing.BadSignature:
            raise serializers.ValidationError({"token": ["Invalid verification link."]})

        try:
            # matching the email too means a link dies if the address on the account changes
            user = User.objects.get(pk=payload["uid"], email=payload["email"])
        except (User.DoesNotExist, KeyError):
            raise serializers.ValidationError({"token": ["Invalid verification link."]})

        attrs["user"] = user
        return attrs 
class UpdateProfileSerializer(serializers.ModelSerializer):
    """Only these fields can be edited. Email, campus and verification status never can."""

    class Meta:
        model = Profile
        fields = ("full_name", "phone")
        extra_kwargs = {"full_name": {"allow_blank": False}}

    def validate_phone(self, value):
        cleaned = re.sub(r"[\s-]", "", value)  # accept "+91 98765-43210"
        if cleaned and not re.fullmatch(r"\+?[0-9]{7,15}", cleaned):
            raise serializers.ValidationError(
                "Enter a valid phone number (7 to 15 digits, optional leading +)."
            )
        return cleaned


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": ["Passwords do not match."]}
            )
        try:
            validate_password(attrs["new_password"], user=self.context["request"].user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        with transaction.atomic():
            user.set_password(self.validated_data["new_password"])
            user.save(update_fields=["password"])
            # log the account out everywhere: revoke every refresh token it has
            for token in OutstandingToken.objects.filter(user=user):
                BlacklistedToken.objects.get_or_create(token=token)
        return user           