from django.db import IntegrityError, transaction
from django.test import TestCase
# --- add to the imports at the top ---
from django.core import mail, signing
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from .tokens import make_verification_token
from .models import AllowedEmailDomain, Profile, User


class ProfileSignalTests(TestCase):
    def test_profile_is_created_with_user(self):
        user = User.objects.create_user(email="a@college.edu", password="StrongPass123!")
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_profile_is_deleted_with_user(self):
        user = User.objects.create_user(email="b@college.edu", password="StrongPass123!")
        user.delete()
        self.assertEqual(Profile.objects.count(), 0)

    def test_only_one_profile_per_user(self):
        user = User.objects.create_user(email="c@college.edu", password="StrongPass123!")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Profile.objects.create(user=user)


class AllowedEmailDomainTests(TestCase):
    def test_domain_is_normalised(self):
        domain = AllowedEmailDomain.objects.create(domain="  @College.EDU ")
        self.assertEqual(domain.domain, "college.edu")

    def test_domain_is_unique_ignoring_case(self):
        AllowedEmailDomain.objects.create(domain="college.edu")
        with self.assertRaises(IntegrityError), transaction.atomic():
            AllowedEmailDomain.objects.create(domain="COLLEGE.edu")
# --- add at the bottom of the file ---
class RegistrationTests(APITestCase):
    def setUp(self):
        AllowedEmailDomain.objects.create(domain="college.edu")
        self.url = reverse("auth-register")
        self.payload = {
            "email": "Student@College.edu",
            "password": "Str0ng-Campus-Pass",
            "full_name": "Test Student",
        }

    def test_register_with_allowed_domain(self):
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="student@college.edu")
        self.assertFalse(user.is_email_verified)
        self.assertEqual(user.profile.full_name, "Test Student")

    def test_password_is_hashed(self):
        self.client.post(self.url, self.payload, format="json")
        user = User.objects.get(email="student@college.edu")
        self.assertNotEqual(user.password, self.payload["password"])
        self.assertTrue(user.check_password(self.payload["password"]))

    def test_verification_email_is_sent(self):
        self.client.post(self.url, self.payload, format="json")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/verify-email/", mail.outbox[0].body)

    def test_blocked_domain_is_rejected(self):
        self.payload["email"] = "someone@gmail.com"
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)
        self.assertEqual(User.objects.count(), 0)

    def test_inactive_domain_is_rejected(self):
        AllowedEmailDomain.objects.filter(domain="college.edu").update(is_active=False)
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_duplicate_email_is_rejected(self):
        self.client.post(self.url, self.payload, format="json")
        self.payload["email"] = "student@college.edu"
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), 1)

    def test_weak_password_is_rejected(self):
        self.payload["password"] = "12345678"
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)

    def test_missing_fields_are_rejected(self):
        response = self.client.post(self.url, {"email": "a@college.edu"}, format="json")
        self.assertEqual(response.status_code, 400)


class EmailVerificationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="v@college.edu", password="Str0ng-Campus-Pass"
        )
        self.url = reverse("auth-verify-email")

    def test_valid_token_verifies_user(self):
        token = make_verification_token(self.user)
        response = self.client.post(self.url, {"token": token}, format="json")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)

    def test_verifying_twice_is_harmless(self):
        token = make_verification_token(self.user)
        self.client.post(self.url, {"token": token}, format="json")
        response = self.client.post(self.url, {"token": token}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_tampered_token_is_rejected(self):
        token = make_verification_token(self.user) + "x"
        response = self.client.post(self.url, {"token": token}, format="json")
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_email_verified)

    def test_garbage_token_is_rejected(self):
        response = self.client.post(self.url, {"token": "not-a-token"}, format="json")
        self.assertEqual(response.status_code, 400)

    @override_settings(EMAIL_VERIFICATION_MAX_AGE=-1)
    def test_expired_token_is_rejected(self):
        token = make_verification_token(self.user)
        response = self.client.post(self.url, {"token": token}, format="json")
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_email_verified)

    def test_token_for_deleted_user_is_rejected(self):
        token = make_verification_token(self.user)
        self.user.delete()
        response = self.client.post(self.url, {"token": token}, format="json")
        self.assertEqual(response.status_code, 400)            