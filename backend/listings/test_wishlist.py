from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status

from .models import Listing, WishlistItem
from .test_api import ListingAPITestCase


class WishlistTests(ListingAPITestCase):
    def setUp(self):
        super().setUp()
        self.listing = self.make_listing(title="Calculator")
        self.url = reverse("wishlist")
        self.client.force_authenticate(user=self.other)  # a buyer, not the seller

    def remove_url(self, listing):
        return reverse("wishlist-remove", args=[listing.id])

    def save(self, listing):
        return self.client.post(self.url, {"listing": listing.id}, format="json")

    def test_wishlist_requires_authentication(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            self.client.post(self.url, {"listing": self.listing.id}, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.delete(self.remove_url(self.listing)).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_save_a_listing(self):
        response = self.save(self.listing)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["listing"]["title"], "Calculator")
        self.assertTrue(response.data["listing"]["is_wishlisted"])
        self.assertEqual(WishlistItem.objects.filter(user=self.other).count(), 1)

    def test_saving_twice_is_harmless(self):
        self.save(self.listing)
        response = self.save(self.listing)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(WishlistItem.objects.count(), 1)

    def test_database_blocks_duplicates_even_if_the_api_is_bypassed(self):
        WishlistItem.objects.create(user=self.other, listing=self.listing)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WishlistItem.objects.create(user=self.other, listing=self.listing)

    def test_cannot_save_your_own_listing(self):
        self.client.force_authenticate(user=self.seller)
        response = self.save(self.listing)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("listing", response.data)

    def test_cannot_save_hidden_or_missing_listings(self):
        hidden = self.make_listing(title="Hidden", is_hidden=True)
        self.assertEqual(self.save(hidden).status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post(self.url, {"listing": 999999}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(WishlistItem.objects.count(), 0)

    def test_list_shows_only_my_items_newest_first(self):
        second = self.make_listing(title="Notes")
        self.save(self.listing)
        self.save(second)
        third = self.make_user("third@college.test")
        WishlistItem.objects.create(user=third, listing=self.listing)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        titles = [item["listing"]["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Notes", "Calculator"])

    def test_hidden_listings_leave_the_wishlist_but_sold_ones_stay(self):
        sold = self.make_listing(title="Sold thing")
        self.save(self.listing)
        self.save(sold)

        Listing.objects.filter(pk=self.listing.pk).update(is_hidden=True)
        Listing.objects.filter(pk=sold.pk).update(status=Listing.Status.SOLD)

        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual([item["listing"]["title"] for item in results], ["Sold thing"])
        self.assertEqual(results[0]["listing"]["status"], "sold")

    def test_remove_is_idempotent_and_only_touches_my_entry(self):
        third = self.make_user("third@college.test")
        WishlistItem.objects.create(user=third, listing=self.listing)
        self.save(self.listing)

        first = self.client.delete(self.remove_url(self.listing))
        again = self.client.delete(self.remove_url(self.listing))

        self.assertEqual(first.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(again.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(WishlistItem.objects.filter(user=self.other).exists())
        self.assertTrue(WishlistItem.objects.filter(user=third).exists())

    def test_browse_list_flags_saved_listings(self):
        self.make_listing(title="Not saved")
        self.save(self.listing)

        response = self.client.get(self.list_url)
        flags = {item["title"]: item["is_wishlisted"] for item in response.data["results"]}
        self.assertEqual(flags, {"Calculator": True, "Not saved": False})

        self.client.force_authenticate(user=None)
        anonymous = self.client.get(self.list_url)
        self.assertFalse(any(item["is_wishlisted"] for item in anonymous.data["results"]))

    def test_deleting_a_listing_removes_it_from_wishlists(self):
        self.save(self.listing)
        self.listing.delete()
        self.assertEqual(WishlistItem.objects.count(), 0)

    def test_wishlist_query_count_does_not_grow_with_items(self):
        def count_queries():
            with CaptureQueriesContext(connection) as context:
                self.client.get(self.url)
            return len(context)

        for _ in range(2):
            WishlistItem.objects.create(user=self.other, listing=self.make_listing())
        few = count_queries()
        for _ in range(8):
            WishlistItem.objects.create(user=self.other, listing=self.make_listing())
        many = count_queries()
        self.assertEqual(few, many)