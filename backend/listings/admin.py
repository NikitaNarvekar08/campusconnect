from django.contrib import admin

from .models import Category, Listing, ListingImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 0


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "seller", "category", "price", "condition", "status", "created_at")
    list_filter = ("status", "category", "condition")
    search_fields = ("title", "description", "seller__email")
    list_select_related = ("seller", "category")
    inlines = [ListingImageInline]
    actions = ["mark_removed", "restore_listings"]

    @admin.action(description="Remove selected listings (moderation)")
    def mark_removed(self, request, queryset):
        queryset.update(status=Listing.Status.REMOVED)

    @admin.action(description="Restore selected listings to available")
    def restore_listings(self, request, queryset):
        queryset.update(status=Listing.Status.AVAILABLE)
