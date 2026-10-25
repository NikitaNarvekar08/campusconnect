from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Category, Listing
from .permissions import IsEmailVerifiedOrReadOnly, IsSellerOrReadOnly
from .serializers import CategorySerializer, ListingImageSerializer, ListingSerializer
from .validators import MAX_IMAGES_PER_LISTING


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    pagination_class = None  # only a handful of categories


class ListingViewSet(viewsets.ModelViewSet):
    serializer_class = ListingSerializer
    permission_classes = [IsEmailVerifiedOrReadOnly, IsSellerOrReadOnly]

    def get_queryset(self):
        # select_related / prefetch_related fetch seller, profile, category and
        # images in a fixed number of queries, however many listings are returned.
        queryset = Listing.objects.select_related(
            "seller__profile", "category"
        ).prefetch_related("images")

        if self.action == "list":
            return queryset.filter(status=Listing.Status.AVAILABLE)

        user = self.request.user
        if user.is_authenticated:
            # Owners can still see their own removed listings.
            return queryset.filter(Q(seller=user) | ~Q(status=Listing.Status.REMOVED))
        return queryset.exclude(status=Listing.Status.REMOVED)

    def perform_create(self, serializer):
        # The seller always comes from the authenticated user.
        serializer.save(seller=self.request.user)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def mine(self, request):
        queryset = self.get_queryset().filter(seller=request.user)
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path="images",
        parser_classes=[MultiPartParser, FormParser],
    )
    def add_image(self, request, pk=None):
        listing = self.get_object()  # also runs the owner-only check
        if listing.status == Listing.Status.REMOVED:
            return Response(
                {"detail": "This listing was removed by a moderator."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ListingImageSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        # Lock the listing row so two simultaneous uploads cannot both pass
        # the "max images" check.
        with transaction.atomic():
            Listing.objects.select_for_update().get(pk=listing.pk)
            count = listing.images.count()
            if count >= MAX_IMAGES_PER_LISTING:
                return Response(
                    {"detail": f"A listing can have at most {MAX_IMAGES_PER_LISTING} images."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            serializer.save(listing=listing, position=count)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"images/(?P<image_id>\d+)",
    )
    def remove_image(self, request, pk=None, image_id=None):
        listing = self.get_object()  # owner-only
        image = get_object_or_404(listing.images, pk=image_id)
        image.image.delete(save=False)  # remove the file from disk too
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
