from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from listings.models import Listing, WishlistItem
from listings.test_api import ListingAPITestCase

from .models import ContactRequest


class DashboardTestCase(ListingAPITestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("dashboard")
        self.third = self.make_user("third@college.test")

        # the seller's five listings
        self.a = self.make_listing(title="A available book", price="350.00")
        self.b = self.make_listing(
            title="B available gadget", price="650.00", category=self.category("electronics")
        )
        self.c = self.make_listing(
            title="C sold book", price="500.00", status=Listing.Status.SOLD
        )
        self.d = self.make_listing(
            title="D unavailable pens",
            price="100.00",
            status=Listing.Status.UNAVAILABLE,
            category=self.category("stationery"),
        )
        self.e = self.make_listing(
            title="E hidden gadget",
            price="200.00",
            is_hidden=True,
            category=self.category("electronics"),
        )
        # the other student's two listings
        self.f = self.make_listing(seller=self.other, title="F other's listing")
        self.g = self.make_listing(seller=self.other, title="G other's listing")

        # wishlists: other saved A and B, the seller saved F
        WishlistItem.objects.create(user=self.other, listing=self.a)
        WishlistItem.objects.create(user=self.other, listing=self.b)
        WishlistItem.objects.create(user=self.seller, listing=self.f)

        # requests: two on the seller's listings, two sent by the seller
        ContactRequest.objects.create(listing=self.a, requester=self.other, message="Hi")
        ContactRequest.objects.create(
            listing=self.b,
            requester=self.third,
            message="Hi",
            status=ContactRequest.Status.ACCEPTED,
        )
        ContactRequest.objects.create(listing=self.f, requester=self.seller, message="Hi")
        ContactRequest.objects.create(
            listing=self.g,
            requester=self.seller,
            message="Hi",
            status=ContactRequest.Status.ACCEPTED,
        )

    def category(self, slug):
        from listings.models import Category

        return Category.objects.get(slug=slug)

    def dashboard(self, user):
        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response


class DashboardStatsTests(DashboardTestCase):
    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_new_student_gets_zeros_and_empty_lists(self):
        newcomer = self.make_user("newcomer@college.test")
        data = self.dashboard(newcomer).data
        self.assertEqual(
            data["listings"],
            {
                "total": 0,
                "active": 0,
                "sold": 0,
                "unavailable": 0,
                "hidden": 0,
                "sold_value": "0.00",
            },
        )
        self.assertEqual(data["wishlist_count"], 0)
        self.assertEqual(data["saves_on_my_listings"], 0)
        self.assertEqual(data["listings_by_category"], [])
        self.assertEqual(data["recent_activity"], [])
        self.assertEqual(len(data["listings_over_time"]), 6)
        self.assertTrue(all(month["count"] == 0 for month in data["listings_over_time"]))

    def test_listing_counts(self):
        data = self.dashboard(self.seller).data
        self.assertEqual(
            data["listings"],
            {
                "total": 5,
                "active": 2,  # A and B: available and not hidden
                "sold": 1,
                "unavailable": 1,
                "hidden": 1,
                "sold_value": "500.00",
            },
        )

    def test_wishlist_and_request_stats(self):
        data = self.dashboard(self.seller).data
        self.assertEqual(data["wishlist_count"], 1)
        self.assertEqual(data["saves_on_my_listings"], 2)
        self.assertEqual(data["requests"]["received"], {"total": 2, "pending": 1})
        self.assertEqual(data["requests"]["sent"], {"total": 2, "pending": 1, "accepted": 1})

    def test_each_student_only_sees_their_own_numbers(self):
        data = self.dashboard(self.other).data
        self.assertEqual(data["listings"]["total"], 2)
        self.assertEqual(data["listings"]["active"], 2)
        self.assertEqual(data["listings"]["sold_value"], "0.00")
        self.assertEqual(data["wishlist_count"], 2)  # A and B
        self.assertEqual(data["saves_on_my_listings"], 1)  # the seller saved F
        self.assertEqual(data["requests"]["received"], {"total": 2, "pending": 1})
        self.assertEqual(data["requests"]["sent"], {"total": 1, "pending": 1, "accepted": 0})

    def test_category_breakdown_is_ordered_by_count_then_name(self):
        data = self.dashboard(self.seller).data
        self.assertEqual(
            [(row["slug"], row["count"]) for row in data["listings_by_category"]],
            [("books", 2), ("electronics", 2), ("stationery", 1)],
        )

    def test_listings_over_time_fills_empty_months(self):
        two_months_ago = timezone.now() - timedelta(days=70)
        Listing.objects.filter(pk=self.e.pk).update(created_at=two_months_ago)

        months = self.dashboard(self.seller).data["listings_over_time"]

        self.assertEqual(len(months), 6)
        labels = [row["month"] for row in months]
        self.assertEqual(labels, sorted(labels))  # oldest first
        by_label = {row["month"]: row["count"] for row in months}
        now = timezone.localtime(timezone.now())
        old = timezone.localtime(two_months_ago)
        self.assertEqual(labels[-1], f"{now.year}-{now.month:02d}")
        self.assertEqual(by_label[f"{old.year}-{old.month:02d}"], 1)
        self.assertEqual(sum(by_label.values()), 5)


class DashboardActivityTests(DashboardTestCase):
    def test_recent_activity_is_newest_first_and_anonymous(self):
        # build a fresh timeline for the seller, oldest to newest
        ContactRequest.objects.all().delete()
        WishlistItem.objects.all().delete()
        ContactRequest.objects.create(listing=self.a, requester=self.other, message="Hi")
        ContactRequest.objects.create(
            listing=self.f,
            requester=self.seller,
            message="Hi",
            status=ContactRequest.Status.ACCEPTED,
        )
        ContactRequest.objects.create(
            listing=self.g,
            requester=self.seller,
            message="Hi",
            status=ContactRequest.Status.DECLINED,
        )
        WishlistItem.objects.create(user=self.other, listing=self.b)

        response = self.dashboard(self.seller)
        events = response.data["recent_activity"]

        self.assertEqual(
            [event["type"] for event in events],
            ["listing_saved", "request_declined", "request_accepted", "request_received"],
        )
        for event in events:
            self.assertEqual(
                set(event.keys()), {"type", "text", "timestamp", "listing"}
            )
        body = response.content.decode()
        self.assertNotIn("other@college.test", body)
        self.assertNotIn("+911111111111", body)

    def test_recent_activity_is_limited_to_ten_events(self):
        for index in range(12):
            listing = self.make_listing(title=f"Extra {index}")
            WishlistItem.objects.create(user=self.other, listing=listing)
        events = self.dashboard(self.seller).data["recent_activity"]
        self.assertEqual(len(events), 10)

    def test_query_count_does_not_grow_with_data(self):
        self.client.force_authenticate(user=self.seller)

        def count_queries():
            with CaptureQueriesContext(connection) as context:
                self.client.get(self.url)
            return len(context)

        few = count_queries()
        for index in range(8):
            listing = self.make_listing(title=f"More {index}")
            WishlistItem.objects.create(user=self.other, listing=listing)
            ContactRequest.objects.create(listing=listing, requester=self.other, message="Hi")
        many = count_queries()
        self.assertEqual(few, many)