from django.conf import settings
from django.core.mail import send_mail

from .tokens import make_verification_token


def send_verification_email(user):
    token = make_verification_token(user)
    link = f"{settings.FRONTEND_URL}/verify-email/{token}"
    send_mail(
        subject="Verify your CampusConnect email",
        message=(
            "Welcome to CampusConnect!\n\n"
            f"Confirm your college email by opening this link:\n{link}\n\n"
            "The link expires in 24 hours. If you did not sign up, ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )