import io
import uuid
from django.test import TransactionTestCase, override_settings, SimpleTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.core.files.storage import default_storage
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from unittest.mock import patch, MagicMock
from PIL import Image

from apps.accounts.models import User, ProviderProfile
from apps.portfolio.models import PortfolioItem, PortfolioMedia
from apps.portfolio.serializers import PortfolioMediaSerializer


def create_dummy_image(format_name, size=(10, 10), color="blue"):
    im = Image.new("RGB", size, color)
    buf = io.BytesIO()
    im.save(buf, format=format_name)
    buf.seek(0)
    return SimpleUploadedFile(
        f"test.{format_name.lower()}",
        buf.read(),
        content_type=f"image/{format_name.lower()}",
    )


class PortfolioMediaConstraintTest(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test_prov@example.com", password="password123"
        )
        self.profile = ProviderProfile.objects.create(
            user=self.user,
        )
        self.item = PortfolioItem.objects.create(
            provider_profile=self.profile,
            title="Portfolio Project",
            description="Item desc",
        )

    def test_valid_external_url_only(self):
        media = PortfolioMedia.objects.create(
            item=self.item,
            file_url="https://example.com/image.jpg",
            media_type=PortfolioMedia.MediaType.IMAGE,
        )
        self.assertEqual(media.file_url, "https://example.com/image.jpg")
        self.assertFalse(bool(media.file))

    def test_valid_uploaded_file_only(self):
        dummy_file = SimpleUploadedFile("dummy.jpg", b"fake-jpeg-binary")
        media = PortfolioMedia.objects.create(
            item=self.item,
            file=dummy_file,
            file_url="",
            media_type=PortfolioMedia.MediaType.IMAGE,
        )
        self.assertTrue(bool(media.file))
        self.assertEqual(media.file_url, "")

    def test_neither_source_fails_clean_and_constraint(self):
        media = PortfolioMedia(
            item=self.item,
            file=None,
            file_url="",
            media_type=PortfolioMedia.MediaType.IMAGE,
        )
        with self.assertRaises(ValidationError):
            media.full_clean()

        with self.assertRaises(IntegrityError):
            media.save()

    def test_both_sources_fails_clean_and_constraint(self):
        dummy_file = SimpleUploadedFile("dummy.jpg", b"fake-jpeg-binary")
        media = PortfolioMedia(
            item=self.item,
            file=dummy_file,
            file_url="https://example.com/image.jpg",
            media_type=PortfolioMedia.MediaType.IMAGE,
        )
        with self.assertRaises(ValidationError):
            media.full_clean()

        with self.assertRaises(IntegrityError):
            media.save()

_TEST_LOCAL_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


@override_settings(STORAGES=_TEST_LOCAL_STORAGES)
class PortfolioMediaUploadAPITest(APITransactionTestCase):
    def setUp(self):
        # Create Owner Provider
        self.owner_user = User.objects.create_user(
            email="owner@example.com", password="password123"
        )
        self.owner_profile = ProviderProfile.objects.create(
            user=self.owner_user,
        )
        self.item = PortfolioItem.objects.create(
            provider_profile=self.owner_profile, title="Item 1"
        )

        # Create Other Provider
        self.other_user = User.objects.create_user(
            email="other@example.com", password="password123"
        )
        self.other_profile = ProviderProfile.objects.create(
            user=self.other_user,
        )

        # Create Client
        self.client_user = User.objects.create_user(
            email="client@example.com", password="password123"
        )

        # Client has no ProviderProfile

    def test_owner_uploads_valid_jpeg(self):
        self.client.force_authenticate(user=self.owner_user)
        jpeg_img = create_dummy_image("JPEG")
        url = reverse("portfolio-items-add-media", kwargs={"pk": self.item.pk})
        
        response = self.client.post(url, {"file": jpeg_img}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("resolved_url", response.data)
        
        media_id = response.data["id"]
        media = PortfolioMedia.objects.get(id=media_id)
        self.assertTrue(bool(media.file))
        self.assertEqual(media.mime_type, "image/jpeg")
        self.assertEqual(media.file_size, media.file.size)
        self.assertEqual(media.width, 10)
        self.assertEqual(media.height, 10)
        self.assertIn("portfolio/", media.file.name)
        self.assertTrue(media.file.name.endswith(".jpg"))

    def test_owner_uploads_valid_png(self):
        self.client.force_authenticate(user=self.owner_user)
        png_img = create_dummy_image("PNG")
        url = reverse("portfolio-items-add-media", kwargs={"pk": self.item.pk})
        response = self.client.post(url, {"file": png_img}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["resolved_url"].endswith(".png"))

    def test_anonymous_upload_rejected(self):
        jpeg_img = create_dummy_image("JPEG")
        url = reverse("portfolio-items-add-media", kwargs={"pk": self.item.pk})
        response = self.client.post(url, {"file": jpeg_img}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_client_upload_rejected(self):
        self.client.force_authenticate(user=self.client_user)
        jpeg_img = create_dummy_image("JPEG")
        url = reverse("portfolio-items-add-media", kwargs={"pk": self.item.pk})
        response = self.client.post(url, {"file": jpeg_img}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_provider_upload_rejected(self):
        self.client.force_authenticate(user=self.other_user)
        jpeg_img = create_dummy_image("JPEG")
        url = reverse("portfolio-items-add-media", kwargs={"pk": self.item.pk})
        response = self.client.post(url, {"file": jpeg_img}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_file_rejected(self):
        self.client.force_authenticate(user=self.owner_user)
        url = reverse("portfolio-items-add-media", kwargs={"pk": self.item.pk})
        response = self.client.post(url, {}, format="multipart")
        # Since 'file' is not in request.FILES, it falls back to URL serializer
        # which will report validation errors because file_url is missing
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_svg_rejected(self):
        self.client.force_authenticate(user=self.owner_user)
        svg_file = SimpleUploadedFile("test.svg", b"<svg></svg>", content_type="image/svg+xml")
        url = reverse("portfolio-items-add-media", kwargs={"pk": self.item.pk})
        response = self.client.post(url, {"file": svg_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_gif_rejected(self):
        self.client.force_authenticate(user=self.owner_user)
        gif_img = create_dummy_image("GIF")
        url = reverse("portfolio-items-add-media", kwargs={"pk": self.item.pk})
        response = self.client.post(url, {"file": gif_img}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_corrupt_file_rejected(self):
        self.client.force_authenticate(user=self.owner_user)
        corrupt_file = SimpleUploadedFile("test.jpg", b"not-a-real-image-bytes")
        url = reverse("portfolio-items-add-media", kwargs={"pk": self.item.pk})
        response = self.client.post(url, {"file": corrupt_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(MEDIA_MAX_IMAGE_SIZE_MB=0.0001)
    def test_oversized_file_rejected(self):
        self.client.force_authenticate(user=self.owner_user)
        img = create_dummy_image("JPEG")
        url = reverse("portfolio-items-add-media", kwargs={"pk": self.item.pk})
        response = self.client.post(url, {"file": img}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_throttle_active(self):
        # We need to test that second request fails due to throttle
        from rest_framework.settings import api_settings
        old_rates = api_settings.DEFAULT_THROTTLE_RATES.copy()
        api_settings.DEFAULT_THROTTLE_RATES['media_upload'] = '1/minute'
        try:
            self.client.force_authenticate(user=self.owner_user)
            jpeg_img = create_dummy_image("JPEG")
            url = reverse("portfolio-items-add-media", kwargs={"pk": self.item.pk})
            
            # First request succeeds
            res1 = self.client.post(url, {"file": jpeg_img}, format="multipart")
            self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

            # Second request blocked by throttle
            jpeg_img2 = create_dummy_image("JPEG")
            res2 = self.client.post(url, {"file": jpeg_img2}, format="multipart")
            self.assertEqual(res2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        finally:
            api_settings.DEFAULT_THROTTLE_RATES = old_rates

    @patch("django.db.models.fields.files.FieldFile.save")
    def test_storage_save_failure_creates_no_db_record(self, mock_save):
        mock_save.side_effect = Exception("Storage error")
        self.client.force_authenticate(user=self.owner_user)
        jpeg_img = create_dummy_image("JPEG")
        url = reverse("portfolio-items-add-media", kwargs={"pk": self.item.pk})
        
        before_count = PortfolioMedia.objects.count()
        response = self.client.post(url, {"file": jpeg_img}, format="multipart")
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(PortfolioMedia.objects.count(), before_count)

    @patch("apps.portfolio.models.PortfolioMedia.save")
    def test_db_creation_failure_deletes_storage_file(self, mock_db_save):
        mock_db_save.side_effect = Exception("Database error")
        self.client.force_authenticate(user=self.owner_user)
        jpeg_img = create_dummy_image("JPEG")
        url = reverse("portfolio-items-add-media", kwargs={"pk": self.item.pk})
        
        with patch.object(default_storage, "delete") as mock_delete:
            response = self.client.post(url, {"file": jpeg_img}, format="multipart")
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            # Verify file deletion was attempted on the uploaded file
            mock_delete.assert_called_once()

    def test_owner_replaces_uploaded_media(self):
        self.client.force_authenticate(user=self.owner_user)
        
        # 1. Create first media
        media = PortfolioMedia.objects.create(
            item=self.item,
            file=SimpleUploadedFile("old.jpg", b"old-binary"),
            file_url="",
            media_type=PortfolioMedia.MediaType.IMAGE,
        )
        old_file_name = media.file.name
        
        # 2. Call replace endpoint
        url = reverse("portfolio-media-replace-media", kwargs={"pk": media.pk})
        new_img = create_dummy_image("PNG")
        
        with patch.object(default_storage, "delete") as mock_delete:
            response = self.client.patch(url, {"file": new_img}, format="multipart")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Since this is TransactionTestCase with commit simulation, let's run on_commit
            transaction.on_commit.func = lambda: None  # mock out to trigger immediately
            
            # Verify database is updated
            media.refresh_from_db()
            self.assertTrue(media.file.name.endswith(".png"))
            self.assertEqual(media.mime_type, "image/png")
            self.assertEqual(media.file_url, "")
            
            # Verify deletion of old file was scheduled/triggered
            mock_delete.assert_called_with(old_file_name)

    def test_owner_deletes_uploaded_media(self):
        self.client.force_authenticate(user=self.owner_user)
        
        media = PortfolioMedia.objects.create(
            item=self.item,
            file=SimpleUploadedFile("to_delete.jpg", b"binary"),
            file_url="",
            media_type=PortfolioMedia.MediaType.IMAGE,
        )
        file_name = media.file.name
        
        url = reverse("portfolio-media-detail", kwargs={"pk": media.pk})
        
        with patch.object(default_storage, "delete") as mock_delete:
            response = self.client.delete(url)
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            
            # Verify deleted from DB
            self.assertFalse(PortfolioMedia.objects.filter(id=media.pk).exists())
            # Verify cleanup was triggered
            mock_delete.assert_called_with(file_name)

    def test_portfolio_item_cascade_cleanup_handles_files(self):
        media = PortfolioMedia.objects.create(
            item=self.item,
            file=SimpleUploadedFile("cascade.jpg", b"binary"),
            file_url="",
            media_type=PortfolioMedia.MediaType.IMAGE,
        )
        file_name = media.file.name
        
        with patch.object(default_storage, "delete") as mock_delete:
            # Delete PortfolioItem, which cascades to PortfolioMedia
            self.item.delete()
            # Verify file deletion cleanup was triggered via signal
            mock_delete.assert_called_with(file_name)


class SerializerPriorityTest(SimpleTestCase):
    def test_uploaded_file_priority_in_resolved_url(self):
        # Create a mock object
        media = MagicMock(spec=PortfolioMedia)
        media.file = MagicMock()
        media.file.url = "/media/portfolio/uuid.jpg"
        media.file_url = "https://external.com/image.jpg"
        
        serializer = PortfolioMediaSerializer(media)
        # Context is empty, so it returns absolute url combined with PUBLIC_BACKEND_URL
        resolved = serializer.get_resolved_url(media)
        self.assertEqual(resolved, "http://localhost:8000/media/portfolio/uuid.jpg")

    def test_external_url_fallback(self):
        media = MagicMock(spec=PortfolioMedia)
        media.file = None
        media.file_url = "https://external.com/image.jpg"
        
        serializer = PortfolioMediaSerializer(media)
        resolved = serializer.get_resolved_url(media)
        self.assertEqual(resolved, "https://external.com/image.jpg")


class PortfolioCoverContractTests(APITransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test_prov_cover@example.com", password="password123", role="provider"
        )
        self.profile = ProviderProfile.objects.create(user=self.user)
        self.item = PortfolioItem.objects.create(
            provider_profile=self.profile,
            title="Portfolio Cover Project",
        )

    def test_portfolio_without_media_returns_null_cover(self):
        from apps.portfolio.serializers import PortfolioItemSerializer
        serializer = PortfolioItemSerializer(self.item)
        self.assertIsNone(serializer.data["cover_url"])

    def test_portfolio_with_valid_cover_file_returns_absolute_url(self):
        from apps.portfolio.serializers import PortfolioItemSerializer
        dummy_file = create_dummy_image("JPEG")
        
        media = PortfolioMedia.objects.create(
            item=self.item,
            file=dummy_file,
            media_type=PortfolioMedia.MediaType.IMAGE,
        )
        
        # Mock request to get absolute URL
        request = MagicMock()
        request.build_absolute_uri = lambda url: f"http://testserver/{url.lstrip('/')}"
        
        serializer = PortfolioItemSerializer(self.item, context={"request": request})
        cover_url = serializer.data["cover_url"]
        self.assertIsNotNone(cover_url)
        self.assertTrue(cover_url.startswith("http://testserver/media/portfolio/"))

    def test_portfolio_falls_back_to_first_valid_image_and_skips_video(self):
        from apps.portfolio.serializers import PortfolioItemSerializer
        
        # First item is a video
        PortfolioMedia.objects.create(
            item=self.item,
            file_url="https://example.com/video.mp4",
            media_type=PortfolioMedia.MediaType.VIDEO,
        )
        
        # Second item is a valid image
        dummy_file = create_dummy_image("JPEG")
        PortfolioMedia.objects.create(
            item=self.item,
            file=dummy_file,
            media_type=PortfolioMedia.MediaType.IMAGE,
        )
        
        request = MagicMock()
        request.build_absolute_uri = lambda url: f"http://testserver/{url.lstrip('/')}"
        
        serializer = PortfolioItemSerializer(self.item, context={"request": request})
        cover_url = serializer.data["cover_url"]
        self.assertIsNotNone(cover_url)
        self.assertTrue(cover_url.startswith("http://testserver/media/portfolio/"))

    def test_missing_physical_file_handled_safely(self):
        from apps.portfolio.serializers import PortfolioItemSerializer
        dummy_file = create_dummy_image("JPEG")
        
        media = PortfolioMedia.objects.create(
            item=self.item,
            file=dummy_file,
            media_type=PortfolioMedia.MediaType.IMAGE,
        )
        
        # Mock storage.exists to return False (simulating missing physical file)
        with patch.object(media.file.storage, "exists", return_value=False):
            serializer = PortfolioItemSerializer(self.item)
            cover_url = serializer.data["cover_url"]
            # Should return None because physical file is missing
            self.assertIsNone(cover_url)

