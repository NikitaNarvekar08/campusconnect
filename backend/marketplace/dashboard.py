from datetime import datetime
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from listings.models import Listing, WishlistItem

from .models import ContactRequest

MONTHS_SHOWN = 6
ACTIVITY_LIMIT = 10


def _money(value):
    return f"{(value or Decimal('0')):.2f}"


def _listing_stats(user):
    # one query: every number below is a conditional aggregate over the same rows
    stats = Listing.objects.filter(seller=user).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status=Listing.Status.AVAILABLE, is_hidden=False)),
        sold=Count("id", filter=Q(status=Listing.Status.SOLD)),
        unavailable=Count("id", filter=Q(status=Listing.Status.UNAVAILABLE)),
        hidden=Count("id", filter=Q(is_hidden=True)),
        sold_value=Sum("price", filter=Q(status=Listing.Status.SOLD)),
    )
    stats["sold_value"] = _money(stats["sold_value"])
    return stats


def _request_stats(user):
    received = ContactRequest.objects.filter(listing__seller=user).aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status=ContactRequest.Status.PENDING)),
    )
    sent = ContactRequest.objects.filter(requester=user).aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status=ContactRequest.Status.PENDING)),
        accepted=Count("id", filter=Q(status=ContactRequest.Status.ACCEPTED)),
    )
    return {"received": received, "sent": sent}


def _listings_by_category(user):
    rows = (
        Listing.objects.filter(seller=user)
        .order_by()  # no default ordering inside a GROUP BY
        .values("category__name", "category__slug")
        .annotate(count=Count("id"))
        .order_by("-count", "category__name")
    )
    return [
        {"category": row["category__name"], "slug": row["category__slug"], "count": row["count"]}
        for row in rows
    ]


def _listings_per_month(user, now):
    current = timezone.localtime(now)
    months = []
    year, month = current.year, current.month
    for _ in range(MONTHS_SHOWN):
        months.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    months.reverse()  # oldest first, which is the order a chart wants

    first_year, first_month = months[0]
    start = timezone.make_aware(datetime(first_year, first_month, 1))
    rows = (
        Listing.objects.filter(seller=user, created_at__gte=start)
        .order_by()
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
    )
    counts = {(row["month"].year, row["month"].month): row["count"] for row in rows}
    return [
        {"month": f"{year}-{month:02d}", "count": counts.get((year, month), 0)}
        for year, month in months
    ]


def _event(kind, timestamp, listing, text):
    return {
        "type": kind,
        "text": text,
        "timestamp": timestamp,
        "listing": {"id": listing.id, "title": listing.title},
    }


def _recent_activity(user):
    events = []

    received = (
        ContactRequest.objects.filter(listing__seller=user)
        .select_related("listing")
        .order_by("-created_at", "-id")[:ACTIVITY_LIMIT]
    )
    for item in received:
        events.append(
            _event(
                "request_received",
                item.created_at,
                item.listing,
                f'A student contacted you about "{item.listing.title}".',
            )
        )

    answered = (
        ContactRequest.objects.filter(requester=user)
        .exclude(status=ContactRequest.Status.PENDING)
        .select_related("listing")
        .order_by("-updated_at", "-id")[:ACTIVITY_LIMIT]
    )
    for item in answered:
        events.append(
            _event(
                f"request_{item.status}",
                item.updated_at,
                item.listing,
                f'Your request about "{item.listing.title}" was {item.status}.',
            )
        )

    saved = (
        WishlistItem.objects.filter(listing__seller=user)
        .select_related("listing")
        .order_by("-created_at", "-id")[:ACTIVITY_LIMIT]
    )
    for item in saved:
        # deliberately anonymous: the seller learns that someone is interested, not who
        events.append(
            _event(
                "listing_saved",
                item.created_at,
                item.listing,
                f'Someone saved "{item.listing.title}" to their wishlist.',
            )
        )

    events.sort(key=lambda event: event["timestamp"], reverse=True)
    return events[:ACTIVITY_LIMIT]


def build_dashboard(user):
    return {
        "listings": _listing_stats(user),
        "saves_on_my_listings": WishlistItem.objects.filter(listing__seller=user).count(),
        "wishlist_count": WishlistItem.objects.filter(
            user=user, listing__is_hidden=False
        ).count(),
        "requests": _request_stats(user),
        "listings_by_category": _listings_by_category(user),
        "listings_over_time": _listings_per_month(user, timezone.now()),
        "recent_activity": _recent_activity(user),
    }


class DashboardView(APIView):
    """The logged-in student's numbers. Needs a login (the global default)."""

    def get(self, request):
        return Response(build_dashboard(request.user))