from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers

from .models import AllowedEmailDomain

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