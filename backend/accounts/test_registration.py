from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import AllowedEmailDomain, Campus

User = get_user_model()


class RegistrationTests(APITestCase):
    def setUp(self):
        self.campus = Campus.objects.create(name="Test College")
        AllowedEmailDomain.objects.create(domain="college.test", campus=self.campus)
        self.url = reverse("register")
        self.payload = {
            "email": "Student@College.Test",
            "full_name": "Test Student",
            "password": "StrongPass#2026",
            "password_confirm": "StrongPass#2026",
        }

    def test_successful_registration(self):
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], "student@college.test")
        self.assertEqual(response.data["campus"], "Test College")
        self.assertFalse(response.data["is_email_verified"])
        self.assertNotIn("password", response.data)

        user = User.objects.get(email="student@college.test")
        self.assertTrue(user.check_password("StrongPass#2026"))
        self.assertNotEqual(user.password, "StrongPass#2026")
        self.assertEqual(user.profile.full_name, "Test Student")
        self.assertEqual(user.profile.campus, self.campus)

    def test_rejects_non_college_email(self):
        self.payload["email"] = "someone@gmail.com"
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        self.assertEqual(User.objects.count(), 0)

    def test_rejects_inactive_domain(self):
        AllowedEmailDomain.objects.filter(domain="college.test").update(is_active=False)
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_rejects_duplicate_email_case_insensitively(self):
        self.client.post(self.url, self.payload, format="json")
        self.payload["email"] = "STUDENT@college.test"
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        self.assertEqual(User.objects.count(), 1)

    def test_rejects_mismatched_passwords(self):
        self.payload["password_confirm"] = "Different#2026"
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password_confirm", response.data)

    def test_rejects_weak_password(self):
        self.payload["password"] = self.payload["password_confirm"] = "12345678"
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_rejects_missing_fields(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for field in ("email", "full_name", "password", "password_confirm"):
            self.assertIn(field, response.data)