from django.conf import settings
from django.core import signing
from django.core.mail import send_mail

SALT = "accounts.email-verification"


def make_verification_token(user):
    return signing.dumps({"uid": user.pk, "email": user.email}, salt=SALT)


def read_verification_token(token):
    """Returns the payload. Raises signing.SignatureExpired or signing.BadSignature."""
    return signing.loads(token, salt=SALT, max_age=settings.EMAIL_VERIFICATION_MAX_AGE)


def send_verification_email(user):
    token = make_verification_token(user)
    link = f"{settings.FRONTEND_URL}/verify-email/{token}"
    send_mail(
        subject="Verify your CampusConnect email",
        message=(
            "Welcome to CampusConnect!\n\n"
            "Please verify your college email by opening this link "
            "(it is valid for 24 hours):\n\n"
            f"{link}\n\n"
            "If you did not create this account, you can ignore this email."
        ),
        from_email=None,  # uses DEFAULT_FROM_EMAIL
        recipient_list=[user.email],
    )