import logging

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .emails import send_verification_email
from .serializers import (
    ChangePasswordSerializer,
    CurrentUserSerializer,
    LogoutSerializer,
    RegisterSerializer,
    UpdateProfileSerializer,
    VerifyEmailSerializer,
)

logger = logging.getLogger(__name__)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # A mail problem must not undo a successful registration; the student can request a new link.
        try:
            send_verification_email(user)
        except Exception:
            logger.exception("Could not send verification email to user %s", user.pk)

        profile = user.profile
        return Response(
            {
                "id": user.id,
                "email": user.email,
                "full_name": profile.full_name,
                "campus": profile.campus.name if profile.campus else None,
                "is_email_verified": user.is_email_verified,
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        if not user.is_email_verified:  # opening the link twice is harmless
            user.is_email_verified = True
            user.save(update_fields=["is_email_verified"])
        return Response({"detail": "Email verified."})


class ResendVerificationView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "resend-verification"

    def post(self, request):
        user = request.user
        if user.is_email_verified:
            return Response(
                {"detail": "Email is already verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        send_verification_email(user)
        return Response({"detail": "Verification email sent."})


class MeView(APIView):
    """The logged-in student. GET to read, PATCH to edit name and phone."""

    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)

    def patch(self, request):
        serializer = UpdateProfileSerializer(
            request.user.profile, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CurrentUserSerializer(request.user).data)


class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password changed. Please log in again."})


class LogoutView(APIView):
    def post(self, request):
        serializer = LogoutSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)