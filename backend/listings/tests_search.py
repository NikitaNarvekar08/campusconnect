from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Category, Listing
from .tests_api import make_listing, make_user


class SearchTestBase(APITestCase):
    def setUp(self):
        self.seller = make_user("seller@college.edu")
        self.url = reverse("listing-list")
        self.books = Category.objects.get(slug="books")
        self.electronics = Category.objects.get(slug="electronics")
        self.lab = Category.objects.get(slug="lab-equipment")

    def titles(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        return [item["title"] for item in response.data["results"]]


class SearchTests(SearchTestBase):
    def setUp(self):
        super().setUp()
        make_listing(
            self.seller, title="Casio scientific calculator",
            description="fx-991 works perfectly", category=self.electronics,
        )
        make_listing(
            self.seller, title="Calculus textbook",
            description="Stewart 8th edition", category=self.books,
        )

    def test_search_matches_title(self):
        self.assertEqual(self.titles(search="calculator"), ["Casio scientific calculator"])

    def test_search_matches_description(self):
        self.assertEqual(self.titles(search="Stewart"), ["Calculus textbook"])

    def test_search_is_case_insensitive(self):
        self.assertEqual(self.titles(search="CASIO"), ["Casio scientific calculator"])

    def test_search_with_several_words_requires_all(self):
        self.assertEqual(
            self.titles(search="scientific calculator"), ["Casio scientific calculator"]
        )
        self.assertEqual(self.titles(search="calculator textbook"), [])

    def test_search_with_no_match_returns_empty_list(self):
        self.assertEqual(self.titles(search="zzzzzz"), [])


class FilterTests(SearchTestBase):
    def setUp(self):
        super().setUp()
        make_listing(
            self.seller, title="Old physics book", category=self.books,
            price=Decimal("100"), condition=Listing.Condition.FAIR,
        )
        make_listing(
            self.seller, title="Lab coat", category=self.lab,
            price=Decimal("300"), condition=Listing.Condition.LIKE_NEW,
        )
        make_listing(
            self.seller, title="Arduino kit", category=self.electronics,
            price=Decimal("1500"), condition=Listing.Condition.NEW,
        )
        make_listing(
            self.seller, title="Calculator", category=self.electronics,
            price=Decimal("700"), condition=Listing.Condition.GOOD,
        )

    def test_filter_by_category(self):
        self.assertEqual(self.titles(category="books"), ["Old physics book"])

    def test_filter_by_another_category(self):
        self.assertEqual(
            sorted(self.titles(category="electronics")), ["Arduino kit", "Calculator"]
        )

    def test_unknown_category_returns_empty_list(self):
        self.assertEqual(self.titles(category="nope"), [])

    def test_filter_by_condition(self):
        self.assertEqual(self.titles(condition="good"), ["Calculator"])

    def test_filter_by_several_conditions(self):
        self.assertEqual(
            sorted(self.titles(condition=["good", "new"])), ["Arduino kit", "Calculator"]
        )

    def test_invalid_condition_is_400(self):
        response = self.client.get(self.url, {"condition": "broken"})
        self.assertEqual(response.status_code, 400)

    def test_filter_by_min_price(self):
        self.assertEqual(
            sorted(self.titles(min_price="700")), ["Arduino kit", "Calculator"]
        )

    def test_filter_by_max_price(self):
        self.assertEqual(
            sorted(self.titles(max_price="300")), ["Lab coat", "Old physics book"]
        )

    def test_filter_by_price_range(self):
        self.assertEqual(
            sorted(self.titles(min_price="300", max_price="700")), ["Calculator", "Lab coat"]
        )

    def test_invalid_price_is_400(self):
        response = self.client.get(self.url, {"min_price": "abc"})
        self.assertEqual(response.status_code, 400)

    def test_filters_combine(self):
        self.assertEqual(
            self.titles(category="electronics", max_price="1000"), ["Calculator"]
        )

    def test_sold_listings_never_appear(self):
        make_listing(
            self.seller, title="Sold camera", category=self.electronics,
            status=Listing.Status.SOLD,
        )
        self.assertNotIn("Sold camera", self.titles(category="electronics"))


class SortTests(SearchTestBase):
    def setUp(self):
        super().setUp()
        make_listing(self.seller, title="First", price=Decimal("300"))
        make_listing(self.seller, title="Second", price=Decimal("100"))
        make_listing(self.seller, title="Third", price=Decimal("200"))

    def test_default_is_newest_first(self):
        self.assertEqual(self.titles(), ["Third", "Second", "First"])

    def test_sort_by_lowest_price(self):
        self.assertEqual(self.titles(ordering="price"), ["Second", "Third", "First"])

    def test_sort_by_highest_price(self):
        self.assertEqual(self.titles(ordering="-price"), ["First", "Third", "Second"])

    def test_unknown_ordering_field_is_ignored(self):
        self.assertEqual(self.titles(ordering="seller"), ["Third", "Second", "First"])


class PaginationTests(SearchTestBase):
    def test_page_size_parameter_is_respected(self):
        for n in range(3):
            make_listing(self.seller, title=f"Item {n}")
        response = self.client.get(self.url, {"page_size": 2})
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])

    def test_equal_prices_never_repeat_across_pages(self):
        for n in range(5):
            make_listing(self.seller, title=f"Same price {n}", price=Decimal("100"))
        seen = []
        for page in (1, 2, 3):
            response = self.client.get(
                self.url, {"ordering": "price", "page_size": 2, "page": page}
            )
            self.assertEqual(response.status_code, 200)
            seen += [item["id"] for item in response.data["results"]]
        self.assertEqual(len(seen), 5)
        self.assertEqual(len(set(seen)), 5)

    def test_page_out_of_range_is_404(self):
        make_listing(self.seller)
        response = self.client.get(self.url, {"page": 99})
        self.assertEqual(response.status_code, 404)

    def test_mine_supports_search(self):
        make_listing(self.seller, title="Graphing calculator")
        make_listing(self.seller, title="Old notes")
        self.client.force_authenticate(self.seller)
        response = self.client.get(reverse("listing-mine"), {"search": "calc"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
