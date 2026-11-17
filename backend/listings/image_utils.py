import io
import os
import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_PIXELS = 25_000_000  # guards against decompression bombs
MAX_SIDE = 1600  # longest side of the stored image, in pixels

# real image format (as detected by Pillow) -> extensions allowed for it
ALLOWED_FORMATS = {
    "JPEG": {".jpg", ".jpeg"},
    "PNG": {".png"},
    "WEBP": {".webp"},
}
STORED_EXTENSION = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


def validate_image_upload(file):
    """Checks the real content of the upload, not what the client claims it is."""
    if file.size > MAX_UPLOAD_BYTES:
        raise ValidationError("Image must be 5 MB or smaller.")

    try:
        with Image.open(file) as image:
            image_format = image.format
            width, height = image.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError("Upload a valid JPEG, PNG or WebP image.")
    finally:
        file.seek(0)

    allowed_extensions = ALLOWED_FORMATS.get(image_format)
    if allowed_extensions is None:
        raise ValidationError("Only JPEG, PNG and WebP images are allowed.")

    extension = os.path.splitext(file.name)[1].lower()
    if extension not in allowed_extensions:
        raise ValidationError("The file extension does not match the image type.")

    if width * height > MAX_PIXELS:
        raise ValidationError("Image dimensions are too large.")


def sanitize_image(file):
    """Rebuilds the image from its pixels and gives it a random name.

    This drops EXIF metadata (phone photos often contain GPS coordinates) and anything
    hidden inside the original file, and shrinks big photos.
    """
    with Image.open(file) as original:
        image_format = original.format
        image = ImageOps.exif_transpose(original)  # keep the photo upright
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        if image_format == "JPEG" and image.mode != "RGB":
            image = image.convert("RGB")

        save_options = {"JPEG": {"quality": 85, "optimize": True},
                        "PNG": {"optimize": True},
                        "WEBP": {"quality": 85}}[image_format]
        buffer = io.BytesIO()
        image.save(buffer, format=image_format, **save_options)

    name = f"{uuid.uuid4().hex}{STORED_EXTENSION[image_format]}"
    return ContentFile(buffer.getvalue(), name=name)