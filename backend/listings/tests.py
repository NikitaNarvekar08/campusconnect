from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from accounts.models import User

from .models import Category, Listing


def make_listing(seller, category, **kwargs):
    defaults = dict(
        title="Engineering Mathematics",
        description="Lightly used.",
        price=Decimal("250.00"),
        condition=Listing.Condition.GOOD,
    )
    defaults.update(kwargs)
    return Listing.objects.create(seller=seller, category=category, **defaults)


class ListingModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="s@college.edu", password="Str0ng-Campus-Pass")
        self.category = Category.objects.get(slug="books")

    def test_categories_are_seeded(self):
        self.assertEqual(Category.objects.count(), 5)

    def test_new_listing_defaults_to_available(self):
        listing = make_listing(self.user, self.category)
        self.assertEqual(listing.status, Listing.Status.AVAILABLE)

    def test_negative_price_is_rejected_by_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_listing(self.user, self.category, price=Decimal("-1.00"))

    def test_listings_are_ordered_newest_first(self):
        first = make_listing(self.user, self.category, title="First")
        second = make_listing(self.user, self.category, title="Second")
        self.assertEqual(list(Listing.objects.all()), [second, first])

    def test_deleting_user_deletes_their_listings(self):
        make_listing(self.user, self.category)
        self.user.delete()
        self.assertEqual(Listing.objects.count(), 0)

    def test_category_with_listings_cannot_be_deleted(self):
        make_listing(self.user, self.category)
        with self.assertRaises(ProtectedError):
            self.category.delete()
