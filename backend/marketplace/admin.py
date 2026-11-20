from django.contrib import admin

from .models import ContactRequest


@admin.register(ContactRequest)
class ContactRequestAdmin(admin.ModelAdmin):
    list_display = ("listing", "requester", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("listing__title", "requester__email")
    list_select_related = ("listing", "requester")