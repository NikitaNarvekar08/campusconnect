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


class Report(models.Model):
    class Reason(models.TextChoices):
        SPAM = "spam", "Spam"
        SCAM = "scam", "Scam or fraud"
        PROHIBITED = "prohibited", "Prohibited item"
        INAPPROPRIATE = "inappropriate", "Inappropriate content"
        MISLEADING = "misleading", "Misleading or wrong details"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved (action taken)"
        DISMISSED = "dismissed", "Dismissed"

    listing = models.ForeignKey(
        "listings.Listing", on_delete=models.CASCADE, related_name="reports"
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_made"
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    details = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_reports",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "reporter"], name="unique_report_per_listing_and_reporter"
            ),
        ]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="report_status_created_idx"),
        ]

    def __str__(self):
        return f"{self.reporter} reported {self.listing} ({self.reason})"