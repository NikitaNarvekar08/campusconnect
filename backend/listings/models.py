from django.conf import settings
from django.db import models
from django.db.models import Q


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Listing(models.Model):
    class Condition(models.TextChoices):
        NEW = "new", "New"
        LIKE_NEW = "like_new", "Like New"
        GOOD = "good", "Good"
        FAIR = "fair", "Fair"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        SOLD = "sold", "Sold"
        UNAVAILABLE = "unavailable", "Unavailable"

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listings"
    )
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="listings")
    campus = models.ForeignKey(
        "accounts.Campus", on_delete=models.PROTECT, related_name="listings"
    )
    title = models.CharField(max_length=150)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    condition = models.CharField(max_length=20, choices=Condition.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    is_hidden = models.BooleanField(default=False, help_text="Set by moderators to hide a listing.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=0), name="listing_price_non_negative"
            ),
        ]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="listing_status_created_idx"),
            models.Index(fields=["price"], name="listing_price_idx"),
            models.Index(fields=["category", "status"], name="listing_cat_status_idx"),
            models.Index(fields=["campus", "status"], name="listing_campus_status_idx"),
        ]

    def __str__(self):
        return self.title