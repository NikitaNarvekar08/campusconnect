from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RegisterSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
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