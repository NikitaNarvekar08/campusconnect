from django.conf import settings
from django.core import signing

SALT = "accounts.email-verification"


def make_verification_token(user):
    """Signed, timestamped token carrying the user's id."""
    return signing.dumps({"uid": user.pk}, salt=SALT)


def read_verification_token(token):
    """Return the user id, or None if the token is invalid or expired."""
    try:
        data = signing.loads(
            token, salt=SALT, max_age=settings.EMAIL_VERIFICATION_MAX_AGE
        )
    except signing.BadSignature:  # also covers SignatureExpired
        return None
    return data.get("uid")