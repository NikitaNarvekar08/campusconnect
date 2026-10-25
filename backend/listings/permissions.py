from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsEmailVerifiedOrReadOnly(BasePermission):
    """Anyone can read. Writing needs a logged-in user with a verified email."""

    message = "Verify your college email before posting."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.is_email_verified)


class IsSellerOrReadOnly(BasePermission):
    """Object-level rule: only the listing's seller may change or delete it."""

    message = "You can only modify your own listings."

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.seller_id == request.user.id
