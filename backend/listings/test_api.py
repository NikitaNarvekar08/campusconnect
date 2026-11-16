from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Campus

from .models import Category, Listing

User = get_user_model()
PASSWORD = "StrongPass#2026"


class ListingAPITestCase(APITestCase):
    def setUp(self):
        self.campus = Campus.objects.create(name="Test College")
        self.seller = self.make_user(
            "seller@college.test", full_name="Sam Seller", phone="+919876543210"
        )
        self.other = self.make_user("other@college.test", full_name="Olive Other")
        self.books = Category.objects.get(slug="books")
        self.list_url = reverse("listing-list")

    def make_user(self, email, verified=True, campus=True, full_name="", phone=""):
        user = User.objects.create_user(
            email=email, password=PASSWORD, is_email_verified=verified
        )
        profile = user.profile
        profile.full_name = full_name
        profile.phone = phone
        profile.campus = self.campus if campus else None
        profile.save()
        return user

    def make_listing(self, seller=None, **overrides):
        data = {
            "seller": seller or self.seller,
            "category": self.books,
            "campus": self.campus,
            "title": "Engineering Mathematics",
            "description": "Barely used.",
            "price": Decimal("350.00"),
            "condition": Listing.Condition.GOOD,
        }
        data.update(overrides)
        return Listing.objects.create(**data)

    def payload(self, **overrides):
        data = {
            "title": "Casio Scientific Calculator",
            "description": "fx-991, works perfectly.",
            "price": "650.00",
            "condition": "like_new",
            "category": "electronics",
        }
        data.update(overrides)
        return data

    def detail_url(self, listing):
        return reverse("listing-detail", args=[listing.id])


class ListingReadTests(ListingAPITestCase):
    def test_public_list_shows_only_available_visible_listings(self):
        self.make_listing(title="Available")
        self.make_listing(title="Sold", status=Listing.Status.SOLD)
        self.make_listing(title="Hidden", is_hidden=True)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["title"] for item in response.data["results"]], ["Available"])

    def test_seller_private_data_is_not_exposed(self):
        self.make_listing()
        response = self.client.get(self.list_url)
        seller = response.data["results"][0]["seller"]
        self.assertEqual(set(seller.keys()), {"id", "full_name"})
        body = response.content.decode()
        self.assertNotIn("seller@college.test", body)
        self.assertNotIn("+919876543210", body)

    def test_retrieve_visibility_rules(self):
        sold = self.make_listing(status=Listing.Status.SOLD)
        hidden = self.make_listing(is_hidden=True)

        self.assertEqual(self.client.get(self.detail_url(sold)).status_code, 200)
        self.assertEqual(self.client.get(self.detail_url(hidden)).status_code, 404)

        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.get(self.detail_url(hidden)).status_code, 404)

        self.client.force_authenticate(user=self.seller)
        self.assertEqual(self.client.get(self.detail_url(hidden)).status_code, 200)

    def test_pagination(self):
        for index in range(13):
            self.make_listing(title=f"Item {index}")
        first = self.client.get(self.list_url)
        self.assertEqual(first.data["count"], 13)
        self.assertEqual(len(first.data["results"]), 12)
        self.assertIsNotNone(first.data["next"])
        second = self.client.get(self.list_url, {"page": 2})
        self.assertEqual(len(second.data["results"]), 1)

    def test_list_query_count_does_not_grow_with_listings(self):
        def count_queries():
            with CaptureQueriesContext(connection) as context:
                self.client.get(self.list_url)
            return len(context)

        for _ in range(2):
            self.make_listing()
        few = count_queries()
        for _ in range(8):
            self.make_listing()
        many = count_queries()
        self.assertEqual(few, many)

    def test_mine_lists_only_own_listings(self):
        self.make_listing(title="Mine available")
        self.make_listing(title="Mine sold", status=Listing.Status.SOLD)
        self.make_listing(seller=self.other, title="Not mine")

        self.assertEqual(
            self.client.get(reverse("listing-mine")).status_code, status.HTTP_401_UNAUTHORIZED
        )

        self.client.force_authenticate(user=self.seller)
        response = self.client.get(reverse("listing-mine"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)


class ListingCreateTests(ListingAPITestCase):
    def test_create_requires_authentication(self):
        response = self.client.post(self.list_url, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_requires_verified_email(self):
        unverified = self.make_user("new@college.test", verified=False)
        self.client.force_authenticate(user=unverified)
        response = self.client.post(self.list_url, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Listing.objects.count(), 0)

    def test_verified_student_can_create(self):
        self.client.force_authenticate(user=self.seller)
        response = self.client.post(self.list_url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["is_owner"])
        listing = Listing.objects.get()
        self.assertEqual(listing.seller, self.seller)
        self.assertEqual(listing.campus, self.campus)
        self.assertEqual(listing.category.slug, "electronics")
        self.assertEqual(listing.price, Decimal("650.00"))
        self.assertEqual(listing.status, Listing.Status.AVAILABLE)

    def test_client_cannot_choose_seller_or_campus(self):
        self.client.force_authenticate(user=self.seller)
        payload = self.payload(seller=self.other.id, campus="Fake College")
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        listing = Listing.objects.get()
        self.assertEqual(listing.seller, self.seller)
        self.assertEqual(listing.campus, self.campus)

    def test_create_validation(self):
        self.client.force_authenticate(user=self.seller)
        cases = {
            "price": self.payload(price="-5"),
            "category": self.payload(category="does-not-exist"),
            "title": {k: v for k, v in self.payload().items() if k != "title"},
            "condition": self.payload(condition="broken"),
        }
        for field, payload in cases.items():
            with self.subTest(field=field):
                response = self.client.post(self.list_url, payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)
        self.assertEqual(Listing.objects.count(), 0)

    def test_create_requires_a_campus(self):
        nomad = self.make_user("nomad@college.test", campus=False)
        self.client.force_authenticate(user=nomad)
        response = self.client.post(self.list_url, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ListingModifyTests(ListingAPITestCase):
    def test_owner_can_update_and_mark_sold(self):
        listing = self.make_listing()
        self.client.force_authenticate(user=self.seller)
        response = self.client.patch(
            self.detail_url(listing),
            {"title": "Updated title", "price": "500.00", "status": "sold"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        listing.refresh_from_db()
        self.assertEqual(listing.title, "Updated title")
        self.assertEqual(listing.price, Decimal("500.00"))
        self.assertEqual(listing.status, Listing.Status.SOLD)

    def test_other_student_cannot_update(self):
        listing = self.make_listing()
        self.client.force_authenticate(user=self.other)
        response = self.client.patch(
            self.detail_url(listing), {"title": "Hacked"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        listing.refresh_from_db()
        self.assertEqual(listing.title, "Engineering Mathematics")

    def test_anonymous_cannot_update(self):
        listing = self.make_listing()
        response = self.client.patch(
            self.detail_url(listing), {"title": "Hacked"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_owner_can_delete(self):
        listing = self.make_listing()
        self.client.force_authenticate(user=self.seller)
        response = self.client.delete(self.detail_url(listing))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Listing.objects.filter(pk=listing.pk).exists())

    def test_other_student_cannot_delete(self):
        listing = self.make_listing()
        self.client.force_authenticate(user=self.other)
        response = self.client.delete(self.detail_url(listing))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Listing.objects.filter(pk=listing.pk).exists())