import io
import tempfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from PIL import Image
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Category, Listing, ListingImage

PASSWORD = "Str0ng-Campus-Pass"
PAYLOAD = {
    "title": "Calculus Book",
    "description": "Good condition, no markings.",
    "price": "199.50",
    "condition": "good",
    "category": "books",
}


def make_user(email, verified=True):
    return User.objects.create_user(
        email=email, password=PASSWORD, is_email_verified=verified
    )


def make_listing(seller, **kwargs):
    defaults = dict(
        category=Category.objects.get(slug="books"),
        title="Engineering Mathematics",
        description="Lightly used.",
        price=Decimal("250.00"),
        condition=Listing.Condition.GOOD,
    )
    defaults.update(kwargs)
    return Listing.objects.create(seller=seller, **defaults)


def make_image(name="photo.png", size=(20, 20)):
    buffer = io.BytesIO()
    Image.new("RGB", size, "teal").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class ListingReadTests(APITestCase):
    def setUp(self):
        self.owner = make_user("owner@college.edu")
        self.list_url = reverse("listing-list")

    def test_list_shows_only_available(self):
        make_listing(self.owner, title="Visible")
        make_listing(self.owner, title="Sold", status=Listing.Status.SOLD)
        make_listing(self.owner, title="Hidden", status=Listing.Status.REMOVED)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Visible"])

    def test_list_is_paginated(self):
        make_listing(self.owner)
        response = self.client.get(self.list_url)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)

    def test_retrieve_is_public(self):
        listing = make_listing(self.owner)
        response = self.client.get(reverse("listing-detail", args=[listing.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["seller"]["id"], self.owner.id)
        self.assertNotIn("email", response.data["seller"])
        self.assertNotIn("phone", response.data["seller"])

    def test_removed_listing_is_hidden_from_others(self):
        listing = make_listing(self.owner, status=Listing.Status.REMOVED)
        response = self.client.get(reverse("listing-detail", args=[listing.id]))
        self.assertEqual(response.status_code, 404)

    def test_removed_listing_is_visible_to_owner(self):
        listing = make_listing(self.owner, status=Listing.Status.REMOVED)
        self.client.force_authenticate(self.owner)
        response = self.client.get(reverse("listing-detail", args=[listing.id]))
        self.assertEqual(response.status_code, 200)

    def test_list_query_count_does_not_grow(self):
        for n in range(2):
            listing = make_listing(self.owner, title=f"Small {n}")
            ListingImage.objects.create(listing=listing, image=f"listing_images/{n}.png")
        with CaptureQueriesContext(connection) as small:
            self.client.get(self.list_url)
        for n in range(6):
            listing = make_listing(self.owner, title=f"Large {n}")
            ListingImage.objects.create(listing=listing, image=f"listing_images/l{n}.png")
        with CaptureQueriesContext(connection) as large:
            self.client.get(self.list_url)
        self.assertEqual(len(small), len(large))

    def test_categories_endpoint_lists_seeded_categories(self):
        response = self.client.get(reverse("category-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 5)


class ListingWriteTests(APITestCase):
    def setUp(self):
        self.owner = make_user("owner@college.edu")
        self.other = make_user("other@college.edu")
        self.list_url = reverse("listing-list")

    def detail(self, listing):
        return reverse("listing-detail", args=[listing.id])

    def test_create_requires_login(self):
        response = self.client.post(self.list_url, PAYLOAD, format="json")
        self.assertEqual(response.status_code, 401)

    def test_unverified_user_cannot_create(self):
        self.client.force_authenticate(make_user("new@college.edu", verified=False))
        response = self.client.post(self.list_url, PAYLOAD, format="json")
        self.assertEqual(response.status_code, 403)

    def test_create_sets_seller_from_request(self):
        self.client.force_authenticate(self.owner)
        payload = dict(PAYLOAD, seller=self.other.id)  # must be ignored
        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, 201)
        listing = Listing.objects.get(pk=response.data["id"])
        self.assertEqual(listing.seller, self.owner)
        self.assertEqual(response.data["status"], "available")
        self.assertTrue(response.data["is_owner"])

    def test_create_rejects_unknown_category(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.list_url, dict(PAYLOAD, category="nope"), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("category", response.data)

    def test_create_rejects_negative_price(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.list_url, dict(PAYLOAD, price="-5"), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("price", response.data)

    def test_create_cannot_set_removed_status(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.list_url, dict(PAYLOAD, status="removed"), format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_owner_can_update(self):
        listing = make_listing(self.owner)
        self.client.force_authenticate(self.owner)
        response = self.client.patch(self.detail(listing), {"title": "New title"}, format="json")
        self.assertEqual(response.status_code, 200)
        listing.refresh_from_db()
        self.assertEqual(listing.title, "New title")

    def test_owner_can_mark_sold(self):
        listing = make_listing(self.owner)
        self.client.force_authenticate(self.owner)
        response = self.client.patch(self.detail(listing), {"status": "sold"}, format="json")
        self.assertEqual(response.status_code, 200)
        listing.refresh_from_db()
        self.assertEqual(listing.status, Listing.Status.SOLD)

    def test_other_user_cannot_update(self):
        listing = make_listing(self.owner)
        self.client.force_authenticate(self.other)
        response = self.client.patch(self.detail(listing), {"title": "Hacked"}, format="json")
        self.assertEqual(response.status_code, 403)
        listing.refresh_from_db()
        self.assertNotEqual(listing.title, "Hacked")

    def test_anonymous_cannot_update(self):
        listing = make_listing(self.owner)
        response = self.client.patch(self.detail(listing), {"title": "Hacked"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_removed_listing_cannot_be_edited(self):
        listing = make_listing(self.owner, status=Listing.Status.REMOVED)
        self.client.force_authenticate(self.owner)
        response = self.client.patch(self.detail(listing), {"title": "Edit"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_owner_can_delete(self):
        listing = make_listing(self.owner)
        self.client.force_authenticate(self.owner)
        response = self.client.delete(self.detail(listing))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Listing.objects.filter(pk=listing.pk).exists())

    def test_other_user_cannot_delete(self):
        listing = make_listing(self.owner)
        self.client.force_authenticate(self.other)
        response = self.client.delete(self.detail(listing))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Listing.objects.filter(pk=listing.pk).exists())

    def test_mine_returns_only_own_listings(self):
        make_listing(self.owner, title="A")
        make_listing(self.owner, title="B", status=Listing.Status.SOLD)
        make_listing(self.other, title="C")
        self.client.force_authenticate(self.owner)
        response = self.client.get(reverse("listing-mine"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)


class ListingImageTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media = tempfile.TemporaryDirectory()
        cls._override = override_settings(MEDIA_ROOT=cls._media.name)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        cls._media.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.owner = make_user("owner@college.edu")
        self.other = make_user("other@college.edu")
        self.listing = make_listing(self.owner)
        self.upload_url = reverse("listing-add-image", args=[self.listing.id])

    def test_owner_can_upload_image(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(self.upload_url, {"image": make_image()}, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.listing.images.count(), 1)
        self.assertTrue(response.data["image"])

    def test_other_user_cannot_upload_image(self):
        self.client.force_authenticate(self.other)
        response = self.client.post(self.upload_url, {"image": make_image()}, format="multipart")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.listing.images.count(), 0)

    def test_non_image_is_rejected(self):
        self.client.force_authenticate(self.owner)
        fake = SimpleUploadedFile("evil.png", b"not an image", content_type="image/png")
        response = self.client.post(self.upload_url, {"image": fake}, format="multipart")
        self.assertEqual(response.status_code, 400)

    def test_sixth_image_is_rejected(self):
        for n in range(5):
            ListingImage.objects.create(
                listing=self.listing, image=f"listing_images/{n}.png", position=n
            )
        self.client.force_authenticate(self.owner)
        response = self.client.post(self.upload_url, {"image": make_image()}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.listing.images.count(), 5)

    def test_owner_can_delete_image(self):
        image = ListingImage.objects.create(listing=self.listing, image="listing_images/x.png")
        url = reverse("listing-remove-image", kwargs={"pk": self.listing.id, "image_id": image.id})
        self.client.force_authenticate(self.owner)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.listing.images.count(), 0)

    def test_other_user_cannot_delete_image(self):
        image = ListingImage.objects.create(listing=self.listing, image="listing_images/x.png")
        url = reverse("listing-remove-image", kwargs={"pk": self.listing.id, "image_id": image.id})
        self.client.force_authenticate(self.other)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.listing.images.count(), 1)
