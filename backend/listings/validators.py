from rest_framework import serializers

MAX_IMAGE_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_IMAGE_DIMENSION = 4096          # pixels, width or height
MAX_IMAGES_PER_LISTING = 5
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def validate_uploaded_image(value):
    """DRF's ImageField has already opened the file with Pillow, so it is a
    real image. These checks enforce our own size, type and dimension rules."""
    if value.size > MAX_IMAGE_BYTES:
        raise serializers.ValidationError("Image must be 2 MB or smaller.")
    if getattr(value, "content_type", None) not in ALLOWED_IMAGE_TYPES:
        raise serializers.ValidationError("Use a JPEG, PNG or WebP image.")
    width, height = value.image.size
    if max(width, height) > MAX_IMAGE_DIMENSION:
        raise serializers.ValidationError("Image dimensions are too large.")
    return value
