from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from rest_framework import status
from rest_framework.throttling import ScopedRateThrottle

from listings.test_api import PASSWORD, ListingAPITestCase

from .models import Report

User = get_user_model()


class ReportTestCase(ListingAPITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()  # the report endpoint is rate limited, so start every test fresh
        self.listing = self.make_listing(title="Calculator")
        self.url = reverse("report-create")
        self.client.force_authenticate(user=self.other)  # a buyer, not the seller

    def report(self, listing=None, reason="scam", details=""):
        listing = listing or self.listing
        return self.client.post(
            self.url,
            {"listing": listing.id, "reason": reason, "details": details},
            format="json",
        )


class ReportAPITests(ReportTestCase):
    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.report().status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reporter_must_have_a_verified_email(self):
        unverified = self.make_user("new@college.test", verified=False)
        self.client.force_authenticate(user=unverified)
        self.assertEqual(self.report().status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Report.objects.count(), 0)

    def test_student_can_report_a_listing(self):
        response = self.report(reason="scam", details="Asked me to pay in advance")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "open")
        self.assertEqual(response.data["reason"], "scam")
        self.assertNotIn("reporter", response.data)
        report = Report.objects.get()
        self.assertEqual(report.reporter, self.other)
        self.assertEqual(report.details, "Asked me to pay in advance")

    def test_cannot_report_your_own_listing(self):
        self.client.force_authenticate(user=self.seller)
        response = self.report()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("listing", response.data)

    def test_cannot_report_hidden_or_missing_listings(self):
        hidden = self.make_listing(title="Hidden", is_hidden=True)
        self.assertEqual(self.report(hidden).status_code, status.HTTP_400_BAD_REQUEST)
        missing = self.client.post(
            self.url, {"listing": 999999, "reason": "spam"}, format="json"
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Report.objects.count(), 0)

    def test_one_report_per_listing_per_student(self):
        self.assertEqual(self.report().status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.report().status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Report.objects.count(), 1)
        # and the database enforces it even if the API is bypassed
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Report.objects.create(listing=self.listing, reporter=self.other, reason="spam")

    def test_validation(self):
        self.assertEqual(self.report(reason="nonsense").status_code, 400)
        self.assertEqual(self.report(reason="other", details="  ").status_code, 400)
        self.assertEqual(self.report(details="x" * 501).status_code, 400)
        missing_reason = self.client.post(self.url, {"listing": self.listing.id}, format="json")
        self.assertEqual(missing_reason.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Report.objects.count(), 0)

    def test_reports_never_hide_a_listing_automatically(self):
        for index in range(3):
            reporter = self.make_user(f"reporter{index}@college.test")
            self.client.force_authenticate(user=reporter)
            self.assertEqual(self.report().status_code, status.HTTP_201_CREATED)

        self.listing.refresh_from_db()
        self.assertFalse(self.listing.is_hidden)
        self.client.force_authenticate(user=None)
        detail = self.client.get(reverse("listing-detail", args=[self.listing.id]))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

    def test_reporting_is_rate_limited(self):
        listings = [self.make_listing(title=f"Item {index}") for index in range(3)]
        with mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"report": "2/hour"}):
            codes = [self.report(listing).status_code for listing in listings]
        self.assertEqual(codes, [201, 201, status.HTTP_429_TOO_MANY_REQUESTS])

    def test_deleting_a_listing_removes_its_reports(self):
        self.report()
        self.listing.delete()
        self.assertEqual(Report.objects.count(), 0)


class ReportModerationTests(ReportTestCase):
    def setUp(self):
        super().setUp()
        self.changelist = reverse("admin:marketplace_report_changelist")
        self.third = self.make_user("third@college.test")
        self.first = Report.objects.create(
            listing=self.listing, reporter=self.other, reason="scam"
        )
        self.second = Report.objects.create(
            listing=self.listing, reporter=self.third, reason="spam"
        )

    def admin_client(self, user):
        client = Client()
        client.force_login(user)
        return client

    def run_action(self, user, action, reports):
        return self.admin_client(user).post(
            self.changelist,
            {"action": action, "_selected_action": [report.pk for report in reports]},
        )

    def test_admin_can_hide_the_listing_and_resolve_its_reports(self):
        admin = User.objects.create_superuser(email="admin@college.test", password=PASSWORD)
        response = self.run_action(admin, "hide_listings_and_resolve", [self.first])
        self.assertEqual(response.status_code, 302)

        self.listing.refresh_from_db()
        self.assertTrue(self.listing.is_hidden)
        for report in (self.first, self.second):  # the other open report is resolved too
            report.refresh_from_db()
            self.assertEqual(report.status, Report.Status.RESOLVED)
            self.assertEqual(report.reviewed_by, admin)
            self.assertIsNotNone(report.reviewed_at)

        self.client.force_authenticate(user=None)
        detail = self.client.get(reverse("listing-detail", args=[self.listing.id]))
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_dismiss_a_report_without_hiding_anything(self):
        admin = User.objects.create_superuser(email="admin@college.test", password=PASSWORD)
        self.run_action(admin, "dismiss_reports", [self.first])

        self.first.refresh_from_db()
        self.second.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertEqual(self.first.status, Report.Status.DISMISSED)
        self.assertEqual(self.first.reviewed_by, admin)
        self.assertEqual(self.second.status, Report.Status.OPEN)
        self.assertFalse(self.listing.is_hidden)

    def test_staff_without_permission_cannot_moderate(self):
        staff = User.objects.create_user(
            email="staff@college.test", password=PASSWORD, is_staff=True
        )
        response = self.run_action(staff, "hide_listings_and_resolve", [self.first])
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.listing.refresh_from_db()
        self.first.refresh_from_db()
        self.assertFalse(self.listing.is_hidden)
        self.assertEqual(self.first.status, Report.Status.OPEN)