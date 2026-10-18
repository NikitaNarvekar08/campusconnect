from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AllowedEmailDomain, Profile, User


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "is_email_verified", "is_staff", "date_joined")
    list_filter = ("is_email_verified", "is_staff", "is_active")
    search_fields = ("email",)
    inlines = [ProfileInline]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Verification", {"fields": ("is_email_verified",)}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )

    def get_inline_instances(self, request, obj=None):
        # Hide the profile inline on the "add user" page: the signal creates
        # the profile, and a second one would violate the one-to-one rule.
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)


@admin.register(AllowedEmailDomain)
class AllowedEmailDomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("domain",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "full_name", "college_name", "updated_at")
    search_fields = ("user__email", "full_name", "college_name")
    list_select_related = ("user",)