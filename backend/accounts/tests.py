from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

User = get_user_model()


class UserManagerTests(TestCase):
    def test_create_user_normalizes_email_and_hashes_password(self):
        user = User.objects.create_user(email="Student@College.EDU", password="StrongPass123")
        self.assertEqual(user.email, "student@college.edu")
        self.assertNotEqual(user.password, "StrongPass123")
        self.assertTrue(user.check_password("StrongPass123"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_email_verified)

    def test_email_is_required(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="StrongPass123")

    def test_duplicate_email_is_rejected_case_insensitively(self):
        User.objects.create_user(email="a@college.edu", password="StrongPass123")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(email="A@College.edu", password="StrongPass123")

    def test_create_superuser_sets_admin_flags(self):
        admin = User.objects.create_superuser(email="admin@college.edu", password="StrongPass123")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_email_verified)