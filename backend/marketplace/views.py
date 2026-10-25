from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from listings.models import Listing

from .models import Wishlist
from .serializers import AddToWishlistSerializer, WishlistSerializer


class WishlistView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WishlistSerializer

    def get_queryset(self):
        # Only my items, and never listings a moderator removed.
        return (
            Wishlist.objects.filter(user=self.request.user)
            .exclude(listing__status=Listing.Status.REMOVED)
            .select_related("listing__seller__profile", "listing__category")
            .prefetch_related("listing__images")
        )

    def create(self, request, *args, **kwargs):
        serializer = AddToWishlistSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        # get_or_create is safe under concurrent requests: if two arrive at once,
        # the database unique constraint rejects one and Django re-reads the row.
        item, created = Wishlist.objects.get_or_create(
            user=request.user, listing=serializer.validated_data["listing"]
        )
        data = WishlistSerializer(item, context={"request": request}).data
        return Response(
            data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class WishlistIdsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ids = Wishlist.objects.filter(user=request.user).values_list(
            "listing_id", flat=True
        )
        return Response({"listing_ids": list(ids)})


class WishlistRemoveView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, listing_id):
        # Filtering by request.user means you can only ever delete your own rows.
        deleted, _ = Wishlist.objects.filter(
            user=request.user, listing_id=listing_id
        ).delete()
        if not deleted:
            return Response(
                {"detail": "This listing is not in your wishlist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
