from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from accounts.models import Campus

from .models import Category, Listing

User = get_user_model()


def make_listing(seller, **overrides):
    data = {
        "seller": seller,
        "category": Category.objects.get(slug="books"),
        "campus": Campus.objects.get_or_create(name="Test College")[0],
        "title": "Engineering Mathematics",
        "description": "Barely used, no markings.",
        "price": Decimal("350.00"),
        "condition": Listing.Condition.GOOD,
    }
    data.update(overrides)
    return Listing.objects.create(**data)


class ListingModelTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(email="s@college.test", password="StrongPass#2026")

    def test_categories_are_seeded(self):
        self.assertEqual(
            set(Category.objects.values_list("slug", flat=True)),
            {"books", "electronics", "stationery", "lab-equipment", "other"},
        )

    def test_new_listing_defaults(self):
        listing = make_listing(self.seller)
        self.assertEqual(listing.status, Listing.Status.AVAILABLE)
        self.assertFalse(listing.is_hidden)
        self.assertEqual(str(listing), "Engineering Mathematics")

    def test_negative_price_is_rejected_by_the_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_listing(self.seller, price=Decimal("-1.00"))

    def test_category_with_listings_cannot_be_deleted(self):
        listing = make_listing(self.seller)
        with self.assertRaises(ProtectedError):
            listing.category.delete()

    def test_deleting_the_seller_deletes_their_listings(self):
        make_listing(self.seller)
        self.seller.delete()
        self.assertEqual(Listing.objects.count(), 0)