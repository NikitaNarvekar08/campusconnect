from decimal import Decimal

from django.urls import reverse
from rest_framework import status

from accounts.models import Campus

from .models import Category, Listing
from .test_api import ListingAPITestCase


class ListingDiscoveryTests(ListingAPITestCase):
    def setUp(self):
        super().setUp()
        self.electronics = Category.objects.get(slug="electronics")
        self.stationery = Category.objects.get(slug="stationery")
        self.other_campus = Campus.objects.create(name="Other College")

        # created oldest to newest
        self.maths = self.make_listing(
            title="Engineering Mathematics",
            description="Kreyszig, 10th edition",
            price=Decimal("350.00"),
            condition=Listing.Condition.GOOD,
        )
        self.calculator = self.make_listing(
            title="Casio fx-991 Calculator",
            description="Scientific, with cover",
            price=Decimal("650.00"),
            condition=Listing.Condition.LIKE_NEW,
            category=self.electronics,
        )
        self.pens = self.make_listing(
            title="Gel pen set",
            description="Pack of 10, unused",
            price=Decimal("120.00"),
            condition=Listing.Condition.NEW,
            category=self.stationery,
            campus=self.other_campus,
        )
        self.laptop = self.make_listing(
            title="Old laptop",
            description="Works, battery weak",
            price=Decimal("15000.00"),
            condition=Listing.Condition.FAIR,
            category=self.electronics,
        )

    def titles(self, **params):
        response = self.client.get(self.list_url, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return [item["title"] for item in response.data["results"]]

    # ---- search ----
    def test_search_matches_title(self):
        self.assertEqual(self.titles(search="calculator"), ["Casio fx-991 Calculator"])

    def test_search_matches_description(self):
        self.assertEqual(self.titles(search="Kreyszig"), ["Engineering Mathematics"])

    def test_search_is_case_insensitive_and_every_word_must_match(self):
        self.assertEqual(self.titles(search="casio SCIENTIFIC"), ["Casio fx-991 Calculator"])
        self.assertEqual(self.titles(search="casio kreyszig"), [])

    def test_search_with_no_match_returns_an_empty_page(self):
        response = self.client.get(self.list_url, {"search": "zzzzzz"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    # ---- filters ----
    def test_filter_by_category(self):
        self.assertCountEqual(
            self.titles(category="electronics"), ["Casio fx-991 Calculator", "Old laptop"]
        )

    def test_filter_by_several_categories(self):
        self.assertCountEqual(
            self.titles(category=["books", "stationery"]),
            ["Engineering Mathematics", "Gel pen set"],
        )

    def test_filter_by_condition(self):
        self.assertEqual(self.titles(condition="new"), ["Gel pen set"])
        self.assertCountEqual(
            self.titles(condition=["new", "like_new"]),
            ["Gel pen set", "Casio fx-991 Calculator"],
        )

    def test_filter_by_price_range(self):
        self.assertCountEqual(
            self.titles(min_price="300", max_price="700"),
            ["Engineering Mathematics", "Casio fx-991 Calculator"],
        )

    def test_filter_by_campus(self):
        self.assertEqual(self.titles(campus=self.other_campus.id), ["Gel pen set"])

    def test_filters_combine(self):
        self.assertEqual(
            self.titles(search="casio", category="electronics", max_price="1000"),
            ["Casio fx-991 Calculator"],
        )

    # ---- sorting ----
    def test_sort_by_lowest_price(self):
        self.assertEqual(
            self.titles(ordering="price"),
            ["Gel pen set", "Engineering Mathematics", "Casio fx-991 Calculator", "Old laptop"],
        )

    def test_sort_by_highest_price(self):
        self.assertEqual(
            self.titles(ordering="-price"),
            ["Old laptop", "Casio fx-991 Calculator", "Engineering Mathematics", "Gel pen set"],
        )

    def test_default_order_is_newest_first_and_unknown_sort_is_ignored(self):
        newest_first = [
            "Old laptop",
            "Gel pen set",
            "Casio fx-991 Calculator",
            "Engineering Mathematics",
        ]
        self.assertEqual(self.titles(), newest_first)
        self.assertEqual(self.titles(ordering="seller__email"), newest_first)

    def test_pagination_is_stable_when_prices_tie(self):
        for index in range(13):
            self.make_listing(title=f"Tie {index}", price=Decimal("100.00"))
        first = self.client.get(self.list_url, {"ordering": "price"})
        second = self.client.get(self.list_url, {"ordering": "price", "page": 2})
        seen = [item["title"] for item in first.data["results"] + second.data["results"]]
        self.assertEqual(len(seen), 17)
        self.assertEqual(len(set(seen)), 17)  # nothing repeated, nothing missing

    # ---- errors, dashboard and lookups ----
    def test_invalid_filter_values_return_400(self):
        for params in (
            {"category": "nope"},
            {"condition": "broken"},
            {"campus": 9999},
            {"min_price": "abc"},
        ):
            with self.subTest(params=params):
                response = self.client.get(self.list_url, params)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mine_can_be_filtered_by_status(self):
        self.make_listing(title="Sold one", status=Listing.Status.SOLD)
        self.client.force_authenticate(user=self.seller)
        response = self.client.get(reverse("listing-mine"), {"status": "sold"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["title"] for item in response.data["results"]], ["Sold one"])

    def test_category_and_campus_lookups_are_public(self):
        categories = self.client.get(reverse("category-list"))
        self.assertEqual(categories.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {item["slug"] for item in categories.data},
            {"books", "electronics", "stationery", "lab-equipment", "other"},
        )

        campuses = self.client.get(reverse("campus-list"))
        self.assertEqual(campuses.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {item["name"] for item in campuses.data}, {"Test College", "Other College"}
        )
        self.assertEqual(set(campuses.data[0].keys()), {"id", "name", "city"})