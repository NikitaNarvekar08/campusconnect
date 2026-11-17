import io
import shutil
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status

from .models import Listing
from .test_api import ListingAPITestCase

TEMP_MEDIA = tempfile.mkdtemp()


def make_image(fmt="PNG", size=(200, 100), name=None, exif=None):
    extension = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp", "GIF": "gif"}[fmt]
    options = {"exif": exif} if exif is not None else {}
    buffer = io.BytesIO()
    Image.new("RGB", size, "red").save(buffer, format=fmt, **options)
    return SimpleUploadedFile(
        name or f"photo.{extension}", buffer.getvalue(), content_type=f"image/{extension}"
    )


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ListingImageTests(ListingAPITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        super().setUp()
        self.listing = self.make_listing()
        self.url = reverse("listing-image", args=[self.listing.id])
        self.storage = Listing._meta.get_field("image").storage
        self.client.force_authenticate(user=self.seller)

    def upload(self, image):
        return self.client.post(self.url, {"image": image}, format="multipart")

    def stored_image(self):
        self.listing.refresh_from_db()
        return self.listing.image

    def test_owner_can_upload_an_image(self):
        response = self.upload(make_image())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        image = self.stored_image()
        self.assertTrue(self.storage.exists(image.name))
        prefix = f"http://testserver/media/listings/{self.seller.id}/"
        self.assertTrue(response.data["image"].startswith(prefix))
        self.assertTrue(response.data["image"].endswith(".png"))

    def test_stored_filename_is_random_not_the_users(self):
        self.upload(make_image(name="my holiday photo.png"))
        self.assertNotIn("holiday", self.stored_image().name)

    def test_only_the_owner_can_upload(self):
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.upload(make_image()).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.upload(make_image()).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(self.stored_image())

    def test_rejects_a_file_that_is_not_an_image(self):
        fake = SimpleUploadedFile("evil.png", b"<?php echo 1; ?>", content_type="image/png")
        response = self.upload(fake)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("image", response.data)
        self.assertFalse(self.stored_image())

    def test_rejects_formats_outside_the_allowlist(self):
        response = self.upload(make_image("GIF"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_extension_that_does_not_match_the_content(self):
        response = self.upload(make_image("PNG", name="photo.jpg"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_files_over_the_size_limit(self):
        with mock.patch("listings.image_utils.MAX_UPLOAD_BYTES", 100):
            response = self.upload(make_image())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_images_with_too_many_pixels(self):
        with mock.patch("listings.image_utils.MAX_PIXELS", 1000):
            response = self.upload(make_image())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_exif_metadata_is_stripped(self):
        exif = Image.Exif()
        exif[271] = "SecretCameraMaker"  # the "Make" tag
        upload = make_image("JPEG", exif=exif)
        self.assertGreater(len(Image.open(io.BytesIO(upload.read())).getexif()), 0)
        upload.seek(0)

        self.upload(upload)

        with self.stored_image().open("rb") as stored, Image.open(stored) as image:
            self.assertEqual(len(image.getexif()), 0)

    def test_large_photos_are_shrunk(self):
        self.upload(make_image("PNG", size=(3000, 2000)))
        with self.stored_image().open("rb") as stored, Image.open(stored) as image:
            self.assertLessEqual(max(image.size), 1600)

    def test_replacing_the_image_deletes_the_old_file(self):
        self.upload(make_image("PNG"))
        old_name = self.stored_image().name
        self.upload(make_image("JPEG"))
        new_name = self.stored_image().name
        self.assertNotEqual(old_name, new_name)
        self.assertFalse(self.storage.exists(old_name))
        self.assertTrue(self.storage.exists(new_name))

    def test_owner_can_remove_the_image(self):
        self.upload(make_image())
        name = self.stored_image().name
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(self.stored_image())
        self.assertFalse(self.storage.exists(name))

    def test_deleting_the_listing_removes_its_file(self):
        self.upload(make_image())
        name = self.stored_image().name
        response = self.client.delete(self.detail_url(self.listing))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(self.storage.exists(name))

    def test_json_body_is_rejected(self):
        response = self.client.post(self.url, {"image": "x"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_listing_without_an_image_shows_null(self):
        response = self.client.get(self.list_url)
        self.assertIsNone(response.data["results"][0]["image"])