from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import AllowedEmailDomain, Campus, Profile

User = get_user_model()


class AllowedEmailDomainTests(TestCase):
    def setUp(self):
        self.campus = Campus.objects.create(name="Test College")

    def test_domain_is_normalized_on_save(self):
        domain = AllowedEmailDomain.objects.create(domain="  @College.EDU ", campus=self.campus)
        self.assertEqual(domain.domain, "college.edu")

    def test_domain_must_be_unique(self):
        AllowedEmailDomain.objects.create(domain="college.edu", campus=self.campus)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AllowedEmailDomain.objects.create(domain="College.edu", campus=self.campus)


class ProfileTests(TestCase):
    def test_profile_is_created_for_new_user(self):
        user = User.objects.create_user(email="s@college.edu", password="StrongPass123")
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_deleting_campus_keeps_the_profile(self):
        campus = Campus.objects.create(name="Test College")
        user = User.objects.create_user(email="s@college.edu", password="StrongPass123")
        Profile.objects.filter(user=user).update(campus=campus)
        campus.delete()
        self.assertIsNone(Profile.objects.get(user=user).campus)

    def test_deleting_user_deletes_the_profile(self):
        user = User.objects.create_user(email="s@college.edu", password="StrongPass123")
        user.delete()
        self.assertEqual(Profile.objects.count(), 0)