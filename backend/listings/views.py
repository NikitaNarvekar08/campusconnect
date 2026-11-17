from django.db.models import Exists, OuterRef, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Campus
from accounts.permissions import IsVerifiedStudent

from .filters import ListingFilter
from .models import Category, Listing, WishlistItem
from .permissions import IsOwner
from .serializers import (
    CampusSerializer,
    CategorySerializer,
    ListingImageSerializer,
    ListingSerializer,
    WishlistAddSerializer,
    WishlistItemSerializer,
)


class ListingViewSet(viewsets.ModelViewSet):
    serializer_class = ListingSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ListingFilter
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "price"]  # allowlist: nothing else can be sorted on
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            permission_classes = [AllowAny]
        elif self.action == "create":
            permission_classes = [IsAuthenticated, IsVerifiedStudent]
        elif self.action == "mine":
            permission_classes = [IsAuthenticated]
        else:  # partial_update, destroy, image
            permission_classes = [IsAuthenticated, IsOwner]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = Listing.objects.select_related("seller__profile", "category", "campus")
        user = self.request.user

        if user.is_authenticated:
            # one EXISTS subquery inside the main query: no extra query per listing
            queryset = queryset.annotate(
                is_wishlisted=Exists(
                    WishlistItem.objects.filter(user=user, listing=OuterRef("pk"))
                )
            )

        if self.action == "list":
            return queryset.filter(is_hidden=False, status=Listing.Status.AVAILABLE)
        if self.action == "mine":
            return queryset.filter(seller=user)
        # retrieve, update, delete: hidden listings exist only for their owner
        if user.is_authenticated:
            return queryset.filter(Q(is_hidden=False) | Q(seller=user))
        return queryset.filter(is_hidden=False)

    def filter_queryset(self, queryset):
        # search, filters and sorting only make sense for the two list-style endpoints
        if self.action not in ("list", "mine"):
            return queryset
        queryset = super().filter_queryset(queryset)
        # a unique tiebreaker keeps pages stable when many listings share a price
        return queryset.order_by(*queryset.query.order_by, "-id")

    def perform_create(self, serializer):
        campus = self.request.user.profile.campus
        if campus is None:
            raise ValidationError({"detail": "Your account is not linked to a campus."})
        serializer.save(seller=self.request.user, campus=campus)

    def perform_destroy(self, instance):
        image = instance.image
        instance.delete()
        if image:
            image.delete(save=False)  # don't leave orphaned files on disk

    @action(detail=False, methods=["get"])
    def mine(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=["post", "delete"],
        url_path="image",
        parser_classes=[MultiPartParser],
    )
    def image(self, request, pk=None):
        listing = self.get_object()  # also runs the owner-only check

        if request.method == "DELETE":
            if listing.image:
                listing.image.delete(save=True)
            return Response(status=204)

        serializer = ListingImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if listing.image:
            listing.image.delete(save=False)  # replace, don't pile up old photos
        listing.image = serializer.validated_data["image"]
        listing.save(update_fields=["image", "updated_at"])
        return Response(self.get_serializer(listing).data)


class CategoryListView(generics.ListAPIView):
    """Public list of categories, for building the filter sidebar."""

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = None


class CampusListView(generics.ListAPIView):
    """Public list of campuses, for building the filter sidebar."""

    queryset = Campus.objects.all()
    serializer_class = CampusSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = None


class WishlistView(generics.ListCreateAPIView):
    """GET: my saved listings. POST: save a listing. Needs a login (the global default)."""

    serializer_class = WishlistItemSerializer

    def get_queryset(self):
        return WishlistItem.objects.filter(
            user=self.request.user, listing__is_hidden=False
        ).select_related(
            "listing__seller__profile", "listing__category", "listing__campus"
        )

    def create(self, request, *args, **kwargs):
        serializer = WishlistAddSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        listing = serializer.validated_data["listing"]

        # atomic get-or-create: safe even if two requests arrive at once, because the
        # unique constraint on (user, listing) rejects the second insert
        item, created = WishlistItem.objects.get_or_create(user=request.user, listing=listing)

        data = WishlistItemSerializer(item, context={"request": request}).data
        return Response(data, status=201 if created else 200)


class WishlistRemoveView(APIView):
    def delete(self, request, listing_id):
        # idempotent: removing something that isn't saved is not an error
        WishlistItem.objects.filter(user=request.user, listing_id=listing_id).delete()
        return Response(status=204)