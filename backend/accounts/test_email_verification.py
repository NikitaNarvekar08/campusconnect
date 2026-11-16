from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .emails import make_verification_token
from .models import AllowedEmailDomain, Campus

User = get_user_model()
PASSWORD = "StrongPass#2026"


class EmailVerificationTests(APITestCase):
    def setUp(self):
        cache.clear()  # the resend endpoint is rate limited, start every test fresh
        campus = Campus.objects.create(name="Test College")
        AllowedEmailDomain.objects.create(domain="college.test", campus=campus)
        self.user = User.objects.create_user(email="s@college.test", password=PASSWORD)
        self.verify_url = reverse("verify-email")
        self.resend_url = reverse("resend-verification")

    def login(self):
        response = self.client.post(
            reverse("login"), {"email": "s@college.test", "password": PASSWORD}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_registration_sends_verification_email(self):
        payload = {
            "email": "new@college.test",
            "full_name": "New Student",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        }
        response = self.client.post(reverse("register"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new@college.test"])
        self.assertIn("/verify-email/", mail.outbox[0].body)

    def test_registration_succeeds_even_if_email_fails(self):
        payload = {
            "email": "new@college.test",
            "full_name": "New Student",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        }
        with patch("accounts.views.send_verification_email", side_effect=RuntimeError("smtp down")):
            response = self.client.post(reverse("register"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="new@college.test").exists())

    def test_valid_token_verifies_email(self):
        token = make_verification_token(self.user)
        response = self.client.post(self.verify_url, {"token": token}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)

    def test_verifying_twice_is_harmless(self):
        token = make_verification_token(self.user)
        self.client.post(self.verify_url, {"token": token}, format="json")
        response = self.client.post(self.verify_url, {"token": token}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_token_is_rejected(self):
        response = self.client.post(self.verify_url, {"token": "garbage"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("token", response.data)

    @override_settings(EMAIL_VERIFICATION_MAX_AGE=-1)
    def test_expired_token_is_rejected(self):
        token = make_verification_token(self.user)
        response = self.client.post(self.verify_url, {"token": token}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_email_verified)

    def test_token_dies_if_account_email_changes(self):
        token = make_verification_token(self.user)
        User.objects.filter(pk=self.user.pk).update(email="changed@college.test")
        response = self.client.post(self.verify_url, {"token": token}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resend_requires_authentication(self):
        response = self.client.post(self.resend_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_resend_sends_email_to_unverified_user(self):
        self.login()
        response = self.client.post(self.resend_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_rejected_if_already_verified(self):
        User.objects.filter(pk=self.user.pk).update(is_email_verified=True)
        self.login()
        response = self.client.post(self.resend_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(mail.outbox), 0)