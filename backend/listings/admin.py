from django.contrib import admin
from django.db.models import Count, Q

from .models import Category, Listing, WishlistItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "seller",
        "category",
        "campus",
        "price",
        "condition",
        "status",
        "is_hidden",
        "open_reports",
        "created_at",
    )
    list_filter = ("status", "condition", "category", "campus", "is_hidden")
    search_fields = ("title", "description", "seller__email")
    list_select_related = ("seller", "category", "campus")
    actions = ["hide_listings", "unhide_listings"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            open_report_count=Count("reports", filter=Q(reports__status="open"))
        )

    @admin.display(description="Open reports", ordering="open_report_count")
    def open_reports(self, obj):
        return obj.open_report_count

    @admin.action(description="Hide selected listings")
    def hide_listings(self, request, queryset):
        queryset.update(is_hidden=True)

    @admin.action(description="Unhide selected listings")
    def unhide_listings(self, request, queryset):
        queryset.update(is_hidden=False)


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("user", "listing", "created_at")
    search_fields = ("user__email", "listing__title")
    list_select_related = ("user", "listing")