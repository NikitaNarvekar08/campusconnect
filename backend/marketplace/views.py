from django.db import transaction
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from accounts.permissions import IsVerifiedStudent

from .filters import ContactRequestFilter
from .models import ContactRequest
from .serializers import (
    ContactRequestCreateSerializer,
    ContactRequestSerializer,
    ReportCreateSerializer,
    ReportSerializer,
)


class ContactRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ContactRequestSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = ContactRequestFilter

    def get_permissions(self):
        if self.action == "create":
            permission_classes = [IsAuthenticated, IsVerifiedStudent]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user
        # you only ever see requests you sent or received: anything else is a 404
        return ContactRequest.objects.filter(
            Q(requester=user) | Q(listing__seller=user)
        ).select_related(
            "listing__seller__profile__campus", "requester__profile__campus"
        )

    def filter_queryset(self, queryset):
        if self.action != "list":
            return queryset
        return super().filter_queryset(queryset)

    def create(self, request, *args, **kwargs):
        serializer = ContactRequestCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        contact_request = serializer.save()
        data = ContactRequestSerializer(contact_request, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.requester_id != request.user.id:
            raise PermissionDenied("Only the sender can cancel a request.")
        if instance.status != ContactRequest.Status.PENDING:
            raise ValidationError({"detail": "Only pending requests can be cancelled."})
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        return self._answer(request, ContactRequest.Status.ACCEPTED)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        return self._answer(request, ContactRequest.Status.DECLINED)

    def _answer(self, request, new_status):
        contact_request = self.get_object()
        if contact_request.listing.seller_id != request.user.id:
            raise PermissionDenied("Only the seller can respond to a request.")

        with transaction.atomic():
            # lock the row so two quick clicks can't both answer the same request
            locked = ContactRequest.objects.select_for_update().get(pk=contact_request.pk)
            if locked.status != ContactRequest.Status.PENDING:
                raise ValidationError({"detail": "This request has already been answered."})
            locked.status = new_status
            locked.save(update_fields=["status", "updated_at"])

        contact_request.refresh_from_db()
        return Response(
            ContactRequestSerializer(contact_request, context={"request": request}).data
        )


class ReportCreateView(generics.CreateAPIView):
    """Students report a listing here. Moderators review reports in the Django admin."""

    serializer_class = ReportCreateSerializer
    permission_classes = [IsAuthenticated, IsVerifiedStudent]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "report"

    def create(self, request, *args, **kwargs):
        serializer = ReportCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        report = serializer.save()
        return Response(ReportSerializer(report).data, status=status.HTTP_201_CREATED)