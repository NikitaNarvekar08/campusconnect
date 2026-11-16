from rest_framework.permissions import BasePermission


class IsVerifiedStudent(BasePermission):
    """Logged-in students whose college email has been verified."""

    message = "Please verify your college email before doing this."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_email_verified)