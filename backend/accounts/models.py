from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Creates users that log in with an email instead of a username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # hashes the password, never stores plaintext
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_email_verified", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None  # we log in with email, so the username field is removed
    email = models.EmailField("email address", unique=True)
    is_email_verified = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # createsuperuser asks only for email and password

    objects = UserManager()

    def __str__(self):
        return self.email


def normalize_domain(value):
    """'  @College.EDU ' -> 'college.edu'"""
    return value.strip().lower().lstrip("@")


class Campus(models.Model):
    name = models.CharField(max_length=120, unique=True)
    city = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "campuses"

    def __str__(self):
        return self.name


class AllowedEmailDomain(models.Model):
    """A college email domain students may register with. Managed in Django Admin."""

    domain = models.CharField(
        max_length=253, unique=True, help_text="Without the @, e.g. college.edu"
    )
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name="email_domains")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["domain"]

    def clean(self):
        # runs before the uniqueness check in forms, so "College.edu" and "college.edu" collide properly
        self.domain = normalize_domain(self.domain)

    def save(self, *args, **kwargs):
        self.domain = normalize_domain(self.domain)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.domain


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    campus = models.ForeignKey(
        Campus, on_delete=models.SET_NULL, null=True, blank=True, related_name="profiles"
    )
    full_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user}"