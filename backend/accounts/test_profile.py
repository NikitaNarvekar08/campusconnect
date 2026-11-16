from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Campus

User = get_user_model()
PASSWORD = "StrongPass#2026"
NEW_PASSWORD = "BrandNewPass#2027"


class BaseAuthTestCase(APITestCase):
    def setUp(self):
        self.campus = Campus.objects.create(name="Test College")
        self.user = User.objects.create_user(email="s@college.test", password=PASSWORD)
        self.user.profile.campus = self.campus
        self.user.profile.save()

    def login(self, password=PASSWORD):
        response = self.client.post(
            reverse("login"), {"email": "s@college.test", "password": password}, format="json"
        )
        if response.status_code == status.HTTP_200_OK:
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        return response


class ProfileUpdateTests(BaseAuthTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("me")

    def test_update_requires_authentication(self):
        response = self.client.patch(self.url, {"full_name": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_full_name_and_phone(self):
        self.login()
        response = self.client.patch(
            self.url, {"full_name": "New Name", "phone": "+91 98765-43210"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["full_name"], "New Name")
        self.assertEqual(response.data["phone"], "+919876543210")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.full_name, "New Name")

    def test_cannot_change_email_campus_or_verification(self):
        self.login()
        response = self.client.patch(
            self.url,
            {
                "full_name": "Name",
                "email": "hacker@college.test",
                "campus": 999,
                "is_email_verified": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "s@college.test")
        self.assertFalse(self.user.is_email_verified)
        self.assertEqual(self.user.profile.campus_id, self.campus.id)

    def test_rejects_blank_full_name(self):
        self.login()
        response = self.client.patch(self.url, {"full_name": "   "}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("full_name", response.data)

    def test_rejects_invalid_phone(self):
        self.login()
        response = self.client.patch(self.url, {"phone": "abc"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", response.data)


class ChangePasswordTests(BaseAuthTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("change-password")

    def payload(self, **overrides):
        data = {
            "old_password": PASSWORD,
            "new_password": NEW_PASSWORD,
            "new_password_confirm": NEW_PASSWORD,
        }
        data.update(overrides)
        return data

    def test_requires_authentication(self):
        response = self.client.post(self.url, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password_and_revoke_sessions(self):
        tokens = self.login().data
        response = self.client.post(self.url, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

        self.client.credentials()
        self.assertEqual(self.login().status_code, status.HTTP_401_UNAUTHORIZED)  # old password
        reuse = self.client.post(
            reverse("token-refresh"), {"refresh": tokens["refresh"]}, format="json"
        )
        self.assertEqual(reuse.status_code, status.HTTP_401_UNAUTHORIZED)  # old session revoked
        self.assertEqual(self.login(password=NEW_PASSWORD).status_code, status.HTTP_200_OK)

    def test_rejects_wrong_old_password(self):
        self.login()
        response = self.client.post(
            self.url, self.payload(old_password="Wrong#Pass2026"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("old_password", response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_rejects_weak_new_password(self):
        self.login()
        response = self.client.post(
            self.url,
            self.payload(new_password="12345678", new_password_confirm="12345678"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.data)

    def test_rejects_mismatched_confirmation(self):
        self.login()
        response = self.client.post(
            self.url, self.payload(new_password_confirm="Different#2027"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password_confirm", response.data)