from decimal import Decimal

from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APITestCase

from listings.models import Listing
from listings.tests_api import make_listing, make_user

from .models import Wishlist


class WishlistModelTests(TestCase):
    def setUp(self):
        self.seller = make_user("seller@college.edu")
        self.buyer = make_user("buyer@college.edu")
        self.listing = make_listing(self.seller)

    def test_duplicate_entry_is_rejected_by_database(self):
        Wishlist.objects.create(user=self.buyer, listing=self.listing)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Wishlist.objects.create(user=self.buyer, listing=self.listing)

    def test_deleting_listing_removes_wishlist_entries(self):
        Wishlist.objects.create(user=self.buyer, listing=self.listing)
        self.listing.delete()
        self.assertEqual(Wishlist.objects.count(), 0)

    def test_deleting_user_removes_wishlist_entries(self):
        Wishlist.objects.create(user=self.buyer, listing=self.listing)
        self.buyer.delete()
        self.assertEqual(Wishlist.objects.count(), 0)


class WishlistApiTests(APITestCase):
    def setUp(self):
        self.seller = make_user("seller@college.edu")
        self.user = make_user("buyer@college.edu")
        self.other = make_user("other@college.edu")
        self.listing = make_listing(self.seller, title="Calculator")
        self.url = reverse("wishlist")

    def test_requires_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.client.post(self.url, {"listing": self.listing.id}).status_code, 401)

    def test_add_listing(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(self.url, {"listing": self.listing.id}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["listing"]["id"], self.listing.id)
        self.assertEqual(Wishlist.objects.filter(user=self.user).count(), 1)

    def test_adding_twice_does_not_duplicate(self):
        self.client.force_authenticate(self.user)
        self.client.post(self.url, {"listing": self.listing.id}, format="json")
        response = self.client.post(self.url, {"listing": self.listing.id}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Wishlist.objects.filter(user=self.user).count(), 1)

    def test_cannot_add_own_listing(self):
        self.client.force_authenticate(self.seller)
        response = self.client.post(self.url, {"listing": self.listing.id}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Wishlist.objects.count(), 0)

    def test_cannot_add_removed_listing(self):
        removed = make_listing(self.seller, status=Listing.Status.REMOVED)
        self.client.force_authenticate(self.user)
        response = self.client.post(self.url, {"listing": removed.id}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_unknown_listing_is_400(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(self.url, {"listing": 999999}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_missing_listing_is_400(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_can_add_sold_listing(self):
        sold = make_listing(self.seller, status=Listing.Status.SOLD)
        self.client.force_authenticate(self.user)
        response = self.client.post(self.url, {"listing": sold.id}, format="json")
        self.assertEqual(response.status_code, 201)

    def test_list_returns_only_own_items(self):
        mine = make_listing(self.seller, title="Mine")
        theirs = make_listing(self.seller, title="Theirs")
        Wishlist.objects.create(user=self.user, listing=mine)
        Wishlist.objects.create(user=self.other, listing=theirs)
        self.client.force_authenticate(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["listing"]["title"], "Mine")

    def test_list_hides_removed_listings(self):
        removed = make_listing(self.seller, status=Listing.Status.REMOVED)
        Wishlist.objects.create(user=self.user, listing=removed)
        self.client.force_authenticate(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.data["count"], 0)

    def test_remove_listing(self):
        Wishlist.objects.create(user=self.user, listing=self.listing)
        self.client.force_authenticate(self.user)
        response = self.client.delete(reverse("wishlist-remove", args=[self.listing.id]))
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Wishlist.objects.count(), 0)

    def test_remove_missing_item_is_404(self):
        self.client.force_authenticate(self.user)
        response = self.client.delete(reverse("wishlist-remove", args=[self.listing.id]))
        self.assertEqual(response.status_code, 404)

    def test_cannot_remove_someone_elses_item(self):
        Wishlist.objects.create(user=self.other, listing=self.listing)
        self.client.force_authenticate(self.user)
        response = self.client.delete(reverse("wishlist-remove", args=[self.listing.id]))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Wishlist.objects.filter(user=self.other).count(), 1)

    def test_ids_endpoint(self):
        first = make_listing(self.seller, title="One")
        second = make_listing(self.seller, title="Two")
        Wishlist.objects.create(user=self.user, listing=first)
        Wishlist.objects.create(user=self.user, listing=second)
        Wishlist.objects.create(user=self.other, listing=self.listing)
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("wishlist-ids"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sorted(response.data["listing_ids"]), sorted([first.id, second.id]))

    def test_list_query_count_does_not_grow(self):
        self.client.force_authenticate(self.user)
        for n in range(2):
            listing = make_listing(self.seller, title=f"Small {n}", price=Decimal("10"))
            Wishlist.objects.create(user=self.user, listing=listing)
        with CaptureQueriesContext(connection) as small:
            self.client.get(self.url)
        for n in range(6):
            listing = make_listing(self.seller, title=f"Large {n}", price=Decimal("10"))
            Wishlist.objects.create(user=self.user, listing=listing)
        with CaptureQueriesContext(connection) as large:
            self.client.get(self.url)
        self.assertEqual(len(small), len(large))
