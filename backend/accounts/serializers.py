from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import AllowedEmailDomain, User


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
        # Passing a user-like object lets Django's similarity validator
        # reject passwords that resemble the email.
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
        # The signal already created an empty Profile; fill in the name.
        user.profile.full_name = validated_data["full_name"]
        user.profile.save(update_fields=["full_name", "updated_at"])
        return user


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField()