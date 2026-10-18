from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.db import models


class UserManager(BaseUserManager):
    """Manager where the email address is the unique identifier."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The email address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # hashes the password
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
    """Custom user that logs in with email instead of username."""

    username = None
    email = models.EmailField(unique=True)
    is_email_verified = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class AllowedEmailDomain(models.Model):
    """A college email domain that may register, e.g. 'mycollege.edu.in'."""

    domain = models.CharField(
        max_length=255,
        unique=True,
        help_text="Domain only, without '@'. Example: mycollege.edu.in",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["domain"]

    @staticmethod
    def _normalise(value):
        return value.strip().lower().lstrip("@")

    def clean(self):
        # Runs before the uniqueness check in Admin and forms,
        # so "College.edu" and "college.edu" are treated as duplicates.
        self.domain = self._normalise(self.domain)

    def save(self, *args, **kwargs):
        # Also normalise on direct saves (shell, code, tests).
        self.domain = self._normalise(self.domain)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.domain


phone_validator = RegexValidator(
    regex=r"^\+?\d{10,15}$",
    message="Enter a valid phone number (10-15 digits, optional leading +).",
)


class Profile(models.Model):
    """Personal details for a user. Created automatically with the user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    full_name = models.CharField(max_length=150, blank=True)
    college_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=16, blank=True, validators=[phone_validator])
    bio = models.TextField(max_length=500, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user.email}"