from django.contrib import admin
from django.db import transaction
from django.utils import timezone

from listings.models import Listing

from .models import ContactRequest, Report


@admin.register(ContactRequest)
class ContactRequestAdmin(admin.ModelAdmin):
    list_display = ("listing", "requester", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("listing__title", "requester__email")
    list_select_related = ("listing", "requester")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("listing", "reason", "status", "reporter", "created_at", "reviewed_by")
    list_filter = ("status", "reason")
    search_fields = ("listing__title", "reporter__email", "details")
    list_select_related = ("listing", "reporter", "reviewed_by")
    readonly_fields = (
        "listing",
        "reporter",
        "reason",
        "details",
        "reviewed_by",
        "reviewed_at",
        "created_at",
    )
    actions = ["hide_listings_and_resolve", "dismiss_reports"]

    def has_add_permission(self, request):
        return False  # reports come only from students, never from the admin

    @admin.action(
        description="Hide the reported listings and mark their reports resolved",
        permissions=["change"],  # only admins who may change reports can run this
    )
    def hide_listings_and_resolve(self, request, queryset):
        listing_ids = set(queryset.values_list("listing_id", flat=True))
        with transaction.atomic():
            Listing.objects.filter(pk__in=listing_ids).update(is_hidden=True)
            Report.objects.filter(
                listing_id__in=listing_ids, status=Report.Status.OPEN
            ).update(
                status=Report.Status.RESOLVED,
                reviewed_by=request.user,
                reviewed_at=timezone.now(),
            )
        self.message_user(
            request, f"Hid {len(listing_ids)} listing(s) and resolved their open reports."
        )

    @admin.action(description="Dismiss selected reports", permissions=["change"])
    def dismiss_reports(self, request, queryset):
        updated = queryset.filter(status=Report.Status.OPEN).update(
            status=Report.Status.DISMISSED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f"Dismissed {updated} report(s).")