from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status

from listings.models import Listing
from listings.test_api import ListingAPITestCase

from .models import ContactRequest

BUYER_EMAIL = "other@college.test"
BUYER_PHONE = "+911111111111"
SELLER_EMAIL = "seller@college.test"
SELLER_PHONE = "+919876543210"


class ContactRequestTestCase(ListingAPITestCase):
    def setUp(self):
        super().setUp()
        # self.seller owns the listing, self.other is the buyer; both have a phone number
        self.other.profile.phone = BUYER_PHONE
        self.other.profile.save()
        self.listing = self.make_listing(title="Calculator")
        self.url = reverse("contact-request-list")
        self.client.force_authenticate(user=self.other)

    def make_request(self, listing=None, requester=None, **overrides):
        data = {
            "listing": listing or self.listing,
            "requester": requester or self.other,
            "message": "Is this still available?",
        }
        data.update(overrides)
        return ContactRequest.objects.create(**data)

    def send(self, listing=None, message="Is this still available?"):
        listing = listing or self.listing
        return self.client.post(
            self.url, {"listing": listing.id, "message": message}, format="json"
        )

    def detail_url(self, contact_request):
        return reverse("contact-request-detail", args=[contact_request.id])

    def answer_url(self, contact_request, action):
        return reverse(f"contact-request-{action}", args=[contact_request.id])


class ContactRequestCreateTests(ContactRequestTestCase):
    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.send().status_code, status.HTTP_401_UNAUTHORIZED)

    def test_sender_must_have_a_verified_email(self):
        unverified = self.make_user("new@college.test", verified=False)
        self.client.force_authenticate(user=unverified)
        self.assertEqual(self.send().status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ContactRequest.objects.count(), 0)

    def test_buyer_can_send_a_request(self):
        response = self.send()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["role"], "sent")
        self.assertEqual(response.data["other_party"]["full_name"], "Sam Seller")
        self.assertNotIn("email", response.data["other_party"])
        self.assertNotIn("phone", response.data["other_party"])
        self.assertEqual(ContactRequest.objects.get().requester, self.other)

    def test_cannot_contact_yourself(self):
        self.client.force_authenticate(user=self.seller)
        response = self.send()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("listing", response.data)

    def test_cannot_contact_about_unavailable_listings(self):
        hidden = self.make_listing(title="Hidden", is_hidden=True)
        sold = self.make_listing(title="Sold", status=Listing.Status.SOLD)
        self.assertEqual(self.send(hidden).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.send(sold).status_code, status.HTTP_400_BAD_REQUEST)
        missing = self.client.post(
            self.url, {"listing": 999999, "message": "Hello"}, format="json"
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ContactRequest.objects.count(), 0)

    def test_one_request_per_listing_per_buyer(self):
        self.assertEqual(self.send().status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.send().status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ContactRequest.objects.count(), 1)
        # and the database enforces it even if the API is bypassed
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_request()

    def test_message_validation(self):
        self.assertEqual(self.send(message="").status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.send(message="   ").status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.send(message="x" * 501).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ContactRequest.objects.count(), 0)


class ContactRequestPrivacyTests(ContactRequestTestCase):
    def test_pending_request_does_not_reveal_the_buyers_contact_details(self):
        self.make_request()
        self.client.force_authenticate(user=self.seller)
        response = self.client.get(self.url)
        item = response.data["results"][0]
        self.assertEqual(item["role"], "received")
        self.assertEqual(item["other_party"]["full_name"], "Olive Other")
        self.assertNotIn("email", item["other_party"])
        self.assertNotIn("phone", item["other_party"])
        body = response.content.decode()
        self.assertNotIn(BUYER_EMAIL, body)
        self.assertNotIn(BUYER_PHONE, body)

    def test_accepting_shares_contact_details_both_ways(self):
        contact_request = self.make_request()
        self.client.force_authenticate(user=self.seller)
        response = self.client.post(self.answer_url(contact_request, "accept"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "accepted")
        self.assertEqual(response.data["other_party"]["email"], BUYER_EMAIL)
        self.assertEqual(response.data["other_party"]["phone"], BUYER_PHONE)

        self.client.force_authenticate(user=self.other)
        buyer_view = self.client.get(self.detail_url(contact_request))
        self.assertEqual(buyer_view.data["other_party"]["email"], SELLER_EMAIL)
        self.assertEqual(buyer_view.data["other_party"]["phone"], SELLER_PHONE)

    def test_declining_keeps_everything_private(self):
        contact_request = self.make_request()
        self.client.force_authenticate(user=self.seller)
        response = self.client.post(self.answer_url(contact_request, "decline"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "declined")
        self.assertNotIn("email", response.data["other_party"])

        self.client.force_authenticate(user=self.other)
        buyer_view = self.client.get(self.detail_url(contact_request))
        self.assertNotIn("email", buyer_view.data["other_party"])
        self.assertNotIn("phone", buyer_view.data["other_party"])

    def test_strangers_see_nothing(self):
        contact_request = self.make_request()
        stranger = self.make_user("third@college.test")
        self.client.force_authenticate(user=stranger)
        self.assertEqual(
            self.client.get(self.detail_url(contact_request)).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(self.client.get(self.url).data["count"], 0)


class ContactRequestWorkflowTests(ContactRequestTestCase):
    def test_only_the_seller_can_respond(self):
        contact_request = self.make_request()
        # the buyer is a party to the request but not the seller
        self.assertEqual(
            self.client.post(self.answer_url(contact_request, "accept")).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        stranger = self.make_user("third@college.test")
        self.client.force_authenticate(user=stranger)
        self.assertEqual(
            self.client.post(self.answer_url(contact_request, "accept")).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.post(self.answer_url(contact_request, "accept")).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        contact_request.refresh_from_db()
        self.assertEqual(contact_request.status, ContactRequest.Status.PENDING)

    def test_a_request_can_only_be_answered_once(self):
        contact_request = self.make_request()
        self.client.force_authenticate(user=self.seller)
        self.assertEqual(
            self.client.post(self.answer_url(contact_request, "accept")).status_code,
            status.HTTP_200_OK,
        )
        again = self.client.post(self.answer_url(contact_request, "decline"))
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)
        contact_request.refresh_from_db()
        self.assertEqual(contact_request.status, ContactRequest.Status.ACCEPTED)

    def test_list_filters(self):
        other_listing = self.make_listing(title="Notes")
        self.make_request()
        accepted = self.make_request(listing=other_listing, message="Hello")
        ContactRequest.objects.filter(pk=accepted.pk).update(
            status=ContactRequest.Status.ACCEPTED
        )

        self.assertEqual(self.client.get(self.url, {"role": "sent"}).data["count"], 2)
        self.assertEqual(self.client.get(self.url, {"role": "received"}).data["count"], 0)
        self.assertEqual(self.client.get(self.url, {"status": "pending"}).data["count"], 1)
        self.assertEqual(
            self.client.get(self.url, {"role": "bogus"}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.client.force_authenticate(user=self.seller)
        self.assertEqual(self.client.get(self.url, {"role": "received"}).data["count"], 2)

    def test_buyer_can_cancel_a_pending_request(self):
        contact_request = self.make_request()
        response = self.client.delete(self.detail_url(contact_request))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ContactRequest.objects.count(), 0)

    def test_cancel_rules(self):
        contact_request = self.make_request()
        self.client.force_authenticate(user=self.seller)
        self.assertEqual(
            self.client.delete(self.detail_url(contact_request)).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        ContactRequest.objects.filter(pk=contact_request.pk).update(
            status=ContactRequest.Status.ACCEPTED
        )
        self.client.force_authenticate(user=self.other)
        self.assertEqual(
            self.client.delete(self.detail_url(contact_request)).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(ContactRequest.objects.count(), 1)

    def test_deleting_a_listing_removes_its_requests(self):
        self.make_request()
        self.listing.delete()
        self.assertEqual(ContactRequest.objects.count(), 0)

    def test_list_query_count_does_not_grow_with_requests(self):
        self.client.force_authenticate(user=self.seller)

        def count_queries():
            with CaptureQueriesContext(connection) as context:
                self.client.get(self.url)
            return len(context)

        for _ in range(2):
            self.make_request(listing=self.make_listing())
        few = count_queries()
        for _ in range(8):
            self.make_request(listing=self.make_listing())
        many = count_queries()
        self.assertEqual(few, many)