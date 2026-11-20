from django.conf import settings
from django.db import models


class ContactRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    listing = models.ForeignKey(
        "listings.Listing", on_delete=models.CASCADE, related_name="contact_requests"
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_requests"
    )
    message = models.CharField(max_length=500)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "requester"], name="unique_request_per_listing_and_buyer"
            ),
        ]
        indexes = [
            models.Index(fields=["requester", "-created_at"], name="request_buyer_created_idx"),
            models.Index(fields=["listing", "status"], name="request_listing_status_idx"),
        ]

    def __str__(self):
        return f"{self.requester} -> {self.listing} ({self.status})"