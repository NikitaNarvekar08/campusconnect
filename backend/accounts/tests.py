from django.db import IntegrityError, transaction
from django.test import TestCase

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