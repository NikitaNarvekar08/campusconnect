from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """Object-level check: only the listing's seller may modify or delete it."""

    message = "You can only modify your own listings."

    def has_object_permission(self, request, view, obj):
        return obj.seller_id == request.user.id