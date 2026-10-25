from django.conf import settings
from django.db import models


class Wishlist(models.Model):
    """One row = one user saving one listing."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )
    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.CASCADE,
        related_name="wishlisted_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "listing"], name="unique_wishlist_entry"
            ),
        ]

    def __str__(self):
        return f"{self.user_id} saved {self.listing_id}"
