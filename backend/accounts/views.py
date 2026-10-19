from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .emails import send_verification_email
from .models import User
from .serializers import RegisterSerializer, VerifyEmailSerializer
from .tokens import read_verification_token


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = serializer.save()
        # Send after the transaction commits so we never email for a user
        # that failed to save.
        send_verification_email(user)
        return Response(
            {
                "message": "Account created. Check your college email to verify it.",
                "email": user.email,
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = read_verification_token(serializer.validated_data["token"])
        if user_id is None:
            return Response(
                {"detail": "This verification link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "This verification link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_email_verified:
            user.is_email_verified = True
            user.save(update_fields=["is_email_verified"])
        return Response({"message": "Email verified. You can now log in."})