from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Campus

User = get_user_model()

PASSWORD = "StrongPass#2026"


class AuthTests(APITestCase):
    def setUp(self):
        self.campus = Campus.objects.create(name="Test College")
        self.user = User.objects.create_user(email="s@college.test", password=PASSWORD)
        self.user.profile.full_name = "Test Student"
        self.user.profile.campus = self.campus
        self.user.profile.save()

        self.login_url = reverse("login")
        self.refresh_url = reverse("token-refresh")
        self.logout_url = reverse("logout")
        self.me_url = reverse("me")

    def login(self, email="s@college.test", password=PASSWORD):
        return self.client.post(
            self.login_url, {"email": email, "password": password}, format="json"
        )

    def authenticate(self):
        tokens = self.login().data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        return tokens

    def test_login_returns_tokens(self):
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_rejects_wrong_password(self):
        response = self.login(password="WrongPass#2026")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_requires_authentication(self):
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_current_user(self):
        self.authenticate()
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "s@college.test")
        self.assertEqual(response.data["full_name"], "Test Student")
        self.assertEqual(response.data["campus"]["name"], "Test College")
        self.assertNotIn("password", response.data)

    def test_me_rejects_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_returns_new_access_token(self):
        tokens = self.login().data
        response = self.client.post(
            self.refresh_url, {"refresh": tokens["refresh"]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_logout_blacklists_refresh_token(self):
        tokens = self.authenticate()
        response = self.client.post(
            self.logout_url, {"refresh": tokens["refresh"]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.client.credentials()
        reuse = self.client.post(
            self.refresh_url, {"refresh": tokens["refresh"]}, format="json"
        )
        self.assertEqual(reuse.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_rejects_other_users_token(self):
        User.objects.create_user(email="other@college.test", password=PASSWORD)
        other_tokens = self.login(email="other@college.test").data

        self.authenticate()
        response = self.client.post(
            self.logout_url, {"refresh": other_tokens["refresh"]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_public_endpoints_stay_public(self):
        response = self.client.get(reverse("health-check"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)