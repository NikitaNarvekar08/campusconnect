from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated

from accounts.permissions import IsVerifiedStudent

from .models import Listing
from .permissions import IsOwner
from .serializers import ListingSerializer


class ListingViewSet(viewsets.ModelViewSet):
    serializer_class = ListingSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            permission_classes = [AllowAny]
        elif self.action == "create":
            permission_classes = [IsAuthenticated, IsVerifiedStudent]
        elif self.action == "mine":
            permission_classes = [IsAuthenticated]
        else:  # partial_update, destroy
            permission_classes = [IsAuthenticated, IsOwner]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = Listing.objects.select_related("seller__profile", "category", "campus")
        user = self.request.user

        if self.action == "list":
            return queryset.filter(is_hidden=False, status=Listing.Status.AVAILABLE)
        if self.action == "mine":
            return queryset.filter(seller=user)
        # retrieve, update, delete: hidden listings exist only for their owner
        if user.is_authenticated:
            return queryset.filter(Q(is_hidden=False) | Q(seller=user))
        return queryset.filter(is_hidden=False)

    def perform_create(self, serializer):
        campus = self.request.user.profile.campus
        if campus is None:
            raise ValidationError({"detail": "Your account is not linked to a campus."})
        serializer.save(seller=self.request.user, campus=campus)

    @action(detail=False, methods=["get"])
    def mine(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)