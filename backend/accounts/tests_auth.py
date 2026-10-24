import io
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APITestCase

from .models import User

PASSWORD = "Str0ng-Campus-Pass"


def make_image(name="avatar.png", fmt="PNG", size=(20, 20)):
    buffer = io.BytesIO()
    Image.new("RGB", size, "teal").save(buffer, format=fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class LoginTests(APITestCase):
    def setUp(self):
        self.verified = User.objects.create_user(
            email="ok@college.edu", password=PASSWORD, is_email_verified=True
        )
        self.unverified = User.objects.create_user(
            email="new@college.edu", password=PASSWORD
        )
        self.url = reverse("auth-login")

    def test_login_returns_tokens(self):
        response = self.client.post(
            self.url, {"email": "ok@college.edu", "password": PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_email_is_case_insensitive(self):
        response = self.client.post(
            self.url, {"email": " OK@College.EDU ", "password": PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, 200)

    def test_wrong_password_is_401(self):
        response = self.client.post(
            self.url, {"email": "ok@college.edu", "password": "wrong"}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_unknown_email_is_401(self):
        response = self.client.post(
            self.url, {"email": "nobody@college.edu", "password": PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_unverified_user_is_403(self):
        response = self.client.post(
            self.url, {"email": "new@college.edu", "password": PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("access", response.data)

    def test_inactive_user_is_rejected(self):
        self.verified.is_active = False
        self.verified.save()
        response = self.client.post(
            self.url, {"email": "ok@college.edu", "password": PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, 401)


class RefreshAndLogoutTests(APITestCase):
    def setUp(self):
        User.objects.create_user(
            email="ok@college.edu", password=PASSWORD, is_email_verified=True
        )
        response = self.client.post(
            reverse("auth-login"),
            {"email": "ok@college.edu", "password": PASSWORD},
            format="json",
        )
        self.refresh = response.data["refresh"]

    def test_refresh_returns_new_tokens(self):
        response = self.client.post(
            reverse("auth-refresh"), {"refresh": self.refresh}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)

    def test_rotated_refresh_token_cannot_be_reused(self):
        self.client.post(reverse("auth-refresh"), {"refresh": self.refresh}, format="json")
        response = self.client.post(
            reverse("auth-refresh"), {"refresh": self.refresh}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_logout_blacklists_refresh_token(self):
        response = self.client.post(
            reverse("auth-logout"), {"refresh": self.refresh}, format="json"
        )
        self.assertEqual(response.status_code, 204)
        response = self.client.post(
            reverse("auth-refresh"), {"refresh": self.refresh}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_logout_with_garbage_token_is_400(self):
        response = self.client.post(
            reverse("auth-logout"), {"refresh": "garbage"}, format="json"
        )
        self.assertEqual(response.status_code, 400)


class MeTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media = tempfile.TemporaryDirectory()
        cls._override = override_settings(MEDIA_ROOT=cls._media.name)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        cls._media.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(
            email="me@college.edu", password=PASSWORD, is_email_verified=True
        )
        response = self.client.post(
            reverse("auth-login"),
            {"email": "me@college.edu", "password": PASSWORD},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        self.url = reverse("auth-me")

    def test_me_requires_authentication(self):
        self.client.credentials()  # remove the token
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_me_returns_user_and_profile(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "me@college.edu")
        self.assertIn("profile", response.data)
        self.assertNotIn("password", response.data)

    def test_patch_updates_profile(self):
        response = self.client.patch(
            self.url,
            {"full_name": "Asha K", "college_name": "Test College", "bio": "Hi"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.full_name, "Asha K")
        self.assertEqual(self.user.profile.college_name, "Test College")

    def test_patch_cannot_change_email_or_verification(self):
        self.client.patch(
            self.url,
            {"email": "hacker@evil.com", "is_email_verified": False},
            format="json",
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "me@college.edu")
        self.assertTrue(self.user.is_email_verified)

    def test_invalid_phone_is_rejected(self):
        response = self.client.patch(self.url, {"phone": "abc"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("phone", response.data)

    def test_avatar_upload_succeeds(self):
        response = self.client.patch(self.url, {"avatar": make_image()}, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["profile"]["avatar"])

    def test_avatar_with_disallowed_format_is_rejected(self):
        gif = make_image(name="a.gif", fmt="GIF")
        response = self.client.patch(self.url, {"avatar": gif}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("avatar", response.data)

    def test_non_image_file_is_rejected(self):
        fake = SimpleUploadedFile("evil.png", b"this is not an image", content_type="image/png")
        response = self.client.patch(self.url, {"avatar": fake}, format="multipart")
        self.assertEqual(response.status_code, 400)

    def test_oversized_avatar_is_rejected(self):
        with mock.patch("accounts.serializers.MAX_AVATAR_BYTES", 10):
            response = self.client.patch(
                self.url, {"avatar": make_image()}, format="multipart"
            )
        self.assertEqual(response.status_code, 400)