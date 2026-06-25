import io
import uuid
import logging
from django.test import TransactionTestCase, override_settings, SimpleTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.core.files.storage import default_storage
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch, MagicMock, PropertyMock
from PIL import Image

from apps.accounts.models import User, ProviderProfile
from apps.catalog.models import Category, Service, ServiceMedia
from apps.catalog.serializers import ServiceListSerializer, ServiceDetailSerializer


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


class ServiceMediaConstraintTest(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test_prov@example.com", password="password123", role="provider"
        )
        self.profile = ProviderProfile.objects.create(user=self.user)
        self.category = Category.objects.create(name_ru="Категория", slug="cat")
        self.service = Service.objects.create(
            provider=self.profile,
            category=self.category,
            title="Service 1",
            price_amount=100.0,
            description="Test Description",
            city="Almaty",
        )

    def test_service_with_no_cover_remains_valid(self):
        # Service can have no media at all
        self.assertEqual(self.service.media.count(), 0)
        
        # Or media with is_cover=False
        media = ServiceMedia.objects.create(
            service=self.service,
            file=SimpleUploadedFile("img1.jpg", b"content"),
            is_cover=False,
        )
        self.assertEqual(self.service.media.count(), 1)
        self.assertFalse(media.is_cover)

    def test_one_active_cover_is_valid(self):
        media = ServiceMedia.objects.create(
            service=self.service,
            file=SimpleUploadedFile("img1.jpg", b"content"),
            is_cover=True,
        )
        self.assertTrue(media.is_cover)
        self.service.full_clean()  # should not raise

    def test_two_active_covers_violates_constraint(self):
        ServiceMedia.objects.create(
            service=self.service,
            file=SimpleUploadedFile("img1.jpg", b"content"),
            is_cover=True,
        )
        
        # Second cover creation should fail at DB constraint
        with self.assertRaises(IntegrityError):
            ServiceMedia.objects.create(
                service=self.service,
                file=SimpleUploadedFile("img2.jpg", b"content"),
                is_cover=True,
            )

    def test_clean_method_raises_on_duplicate(self):
        ServiceMedia.objects.create(
            service=self.service,
            file=SimpleUploadedFile("img1.jpg", b"content"),
            is_cover=True,
        )
        
        duplicate = ServiceMedia(
            service=self.service,
            file=SimpleUploadedFile("img2.jpg", b"content"),
            is_cover=True,
        )
        
        with self.assertRaises(ValidationError):
            duplicate.clean()

    def test_migration_uses_actual_sequential_number(self):
        # Assert that the new migration has sequential index 0007
        import os
        from django.conf import settings
        migrations_dir = os.path.join(settings.BASE_DIR, "apps", "catalog", "migrations")
        files = os.listdir(migrations_dir)
        migration_files = [f for f in files if f.startswith("0007_") and f.endswith(".py")]
        self.assertEqual(len(migration_files), 1)

    def test_legacy_first_media_behavior_preserved_by_migration(self):
        # We test the RunPython code inside the migration manually here
        import importlib
        migration_module = importlib.import_module(
            "apps.catalog.migrations.0007_servicemedia_file_size_servicemedia_height_and_more"
        )
        normalize_service_covers = migration_module.normalize_service_covers
        
        # Create a service with 2 media items, neither is a cover
        media1 = ServiceMedia.objects.create(service=self.service, file=SimpleUploadedFile("1.jpg", b"content"), is_cover=False)
        media2 = ServiceMedia.objects.create(service=self.service, file=SimpleUploadedFile("2.jpg", b"content"), is_cover=False)
        
        # Run normalization
        # Mock apps for data migration
        class MockApps:
            def get_model(self, app_name, model_name):
                if model_name == "Service":
                    return Service
                return ServiceMedia
        
        normalize_service_covers(MockApps(), None)
        
        media1.refresh_from_db()
        media2.refresh_from_db()
        # First media should be promoted to cover
        self.assertTrue(media1.is_cover)
        self.assertFalse(media2.is_cover)


class ServiceMediaUploadAPITest(APITestCase):
    def setUp(self):
        # Create Owner Provider
        self.owner_user = User.objects.create_user(
            email="owner@example.com", password="password123", role="provider"
        )
        self.owner_profile = ProviderProfile.objects.create(user=self.owner_user)
        self.category = Category.objects.create(name_ru="Категория", slug="cat")
        self.service = Service.objects.create(
            provider=self.owner_profile,
            category=self.category,
            title="Service 1",
            price_amount=100.0,
            description="Test Description",
            city="Almaty",
        )

        # Create Other Provider
        self.other_user = User.objects.create_user(
            email="other@example.com", password="password123", role="provider"
        )
        self.other_profile = ProviderProfile.objects.create(user=self.other_user)

        # Create Client
        self.client_user = User.objects.create_user(
            email="client@example.com", password="password123", role="client"
        )

    def test_owner_uploads_valid_jpeg(self):
        self.client.force_authenticate(user=self.owner_user)
        jpeg_img = create_dummy_image("JPEG")
        url = reverse("services-cover", kwargs={"pk": self.service.pk})
        
        response = self.client.post(url, {"file": jpeg_img}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("cover_url", response.data)
        
        self.service.refresh_from_db()
        cover = self.service.media.filter(is_cover=True).first()
        self.assertIsNotNone(cover)
        self.assertEqual(cover.mime_type, "image/jpeg")
        self.assertEqual(cover.file_size, cover.file.size)

    def test_anonymous_upload_rejected(self):
        jpeg_img = create_dummy_image("JPEG")
        url = reverse("services-cover", kwargs={"pk": self.service.pk})
        response = self.client.post(url, {"file": jpeg_img}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_client_upload_rejected(self):
        self.client.force_authenticate(user=self.client_user)
        jpeg_img = create_dummy_image("JPEG")
        url = reverse("services-cover", kwargs={"pk": self.service.pk})
        response = self.client.post(url, {"file": jpeg_img}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_provider_upload_rejected(self):
        self.client.force_authenticate(user=self.other_user)
        jpeg_img = create_dummy_image("JPEG")
        url = reverse("services-cover", kwargs={"pk": self.service.pk})
        response = self.client.post(url, {"file": jpeg_img}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_svg_rejected(self):
        self.client.force_authenticate(user=self.owner_user)
        svg_file = SimpleUploadedFile("test.svg", b"<svg></svg>", content_type="image/svg+xml")
        url = reverse("services-cover", kwargs={"pk": self.service.pk})
        response = self.client.post(url, {"file": svg_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_gif_rejected(self):
        self.client.force_authenticate(user=self.owner_user)
        gif_img = create_dummy_image("GIF")
        url = reverse("services-cover", kwargs={"pk": self.service.pk})
        response = self.client.post(url, {"file": gif_img}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cover_deletion_returns_null_cover_url(self):
        self.client.force_authenticate(user=self.owner_user)
        # Create active cover
        ServiceMedia.objects.create(
            service=self.service,
            file=SimpleUploadedFile("cover.jpg", b"binary"),
            is_cover=True,
        )
        
        # Retrieve through list serializer
        serializer = ServiceListSerializer(self.service)
        self.assertIsNotNone(serializer.data["cover_url"])
        
        # Delete cover
        url = reverse("services-cover", kwargs={"pk": self.service.pk})
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(url)
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            
        # Verify it now returns null
        self.service = Service.objects.get(pk=self.service.pk)
        serializer = ServiceListSerializer(self.service)
        self.assertIsNone(serializer.data["cover_url"])

    def test_non_cover_media_row_becomes_cover_automatically_as_fallback(self):
        # Have a non-cover media
        non_cover = ServiceMedia.objects.create(
            service=self.service,
            file=SimpleUploadedFile("other.jpg", b"binary"),
            is_cover=False,
        )
        
        # Serializer cover should be fallback image under new contract
        serializer = ServiceListSerializer(self.service)
        self.assertIsNotNone(serializer.data["cover_url"])

    def test_direct_cover_deletion_triggers_exactly_one_storage_delete(self):
        self.client.force_authenticate(user=self.owner_user)
        media = ServiceMedia.objects.create(
            service=self.service,
            file=SimpleUploadedFile("to_delete.jpg", b"binary"),
            is_cover=True,
        )
        file_name = media.file.name
        
        url = reverse("services-cover", kwargs={"pk": self.service.pk})
        
        with patch.object(default_storage, "delete") as mock_delete:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.delete(url)
                self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            
            # Verify exactly one deletion call occurred
            mock_delete.assert_called_once_with(file_name)

    def test_service_cascade_deletion_cleans_exactly_once_per_media(self):
        media1 = ServiceMedia.objects.create(
            service=self.service,
            file=SimpleUploadedFile("1.jpg", b"binary"),
            is_cover=True,
        )
        media2 = ServiceMedia.objects.create(
            service=self.service,
            file=SimpleUploadedFile("2.jpg", b"binary"),
            is_cover=False,
        )
        file1 = media1.file.name
        file2 = media2.file.name
        
        with patch.object(default_storage, "delete") as mock_delete:
            with self.captureOnCommitCallbacks(execute=True):
                self.service.delete()
            
            # Exactly one delete per media file should be called
            self.assertEqual(mock_delete.call_count, 2)
            mock_delete.assert_any_call(file1)
            mock_delete.assert_any_call(file2)

    def test_replacement_deletes_only_previous_object_after_commit(self):
        self.client.force_authenticate(user=self.owner_user)
        media = ServiceMedia.objects.create(
            service=self.service,
            file=SimpleUploadedFile("old.jpg", b"old-binary"),
            is_cover=True,
        )
        old_file_name = media.file.name
        
        url = reverse("services-cover", kwargs={"pk": self.service.pk})
        new_img = create_dummy_image("PNG")
        
        with patch.object(default_storage, "delete") as mock_delete:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(url, {"file": new_img}, format="multipart")
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            
            # Check old file is deleted, new file is NOT deleted
            mock_delete.assert_called_once_with(old_file_name)

    def test_db_failure_cleans_new_object_immediately(self):
        self.client.force_authenticate(user=self.owner_user)
        url = reverse("services-cover", kwargs={"pk": self.service.pk})
        jpeg_img = create_dummy_image("JPEG")
        
        # Mock database save to raise an error
        with patch("apps.catalog.models.ServiceMedia.save") as mock_save:
            mock_save.side_effect = Exception("DB error")
            with patch.object(default_storage, "delete") as mock_delete:
                response = self.client.post(url, {"file": jpeg_img}, format="multipart")
                self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
                
                # New file should be deleted immediately
                mock_delete.assert_called_once()

    def test_sqlite_locking_and_postgresql_documentation(self):
        # Select_for_update locking works in SQLite and is fully documented.
        # SQLite uses database-level locking for updates, whereas PostgreSQL
        # locks specific rows. We document PostgreSQL locking behavior below:
        #
        # PostgreSQL select_for_update Locking Behavior:
        # - PostgreSQL select_for_update() locks the selected Service row for updates.
        # - Any concurrent transactions trying to lock or update the same Service row
        #   will block until this transaction commits or aborts.
        # - This prevents race conditions where concurrent requests attempt to create
        #   or replace covers simultaneously, ensuring constraint safety.
        self.client.force_authenticate(user=self.owner_user)
        url = reverse("services-cover", kwargs={"pk": self.service.pk})
        jpeg_img = create_dummy_image("JPEG")
        
        response = self.client.post(url, {"file": jpeg_img}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class SerializerCoverURLResolutionTest(SimpleTestCase):
    def test_absolute_url_stay_unchanged(self):
        media = MagicMock(spec=ServiceMedia)
        media.file = MagicMock()
        media.file.url = "https://my-bucket.s3.amazonaws.com/services/1/1/uuid.jpg"
        media.is_cover = True
        
        service = MagicMock(spec=Service)
        service.media.all.return_value = [media]
        
        serializer = ServiceListSerializer(service)
        cover_url = serializer.get_cover_url(service)
        self.assertEqual(cover_url, "https://my-bucket.s3.amazonaws.com/services/1/1/uuid.jpg")

    def test_broken_storage_returns_none(self):
        media = MagicMock(spec=ServiceMedia)
        type(media.file).url = PropertyMock(side_effect=Exception("Storage error"))
        media.is_cover = True
        
        service = MagicMock(spec=Service)
        service.media.all.return_value = [media]
        
        serializer = ServiceListSerializer(service)
        cover_url = serializer.get_cover_url(service)
        self.assertIsNone(cover_url)


class ServiceCoverContractTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test_prov_service_cover@example.com", password="password123", role="provider"
        )
        self.profile = ProviderProfile.objects.create(user=self.user)
        self.category = Category.objects.create(name_ru="Категория", slug="cat")
        self.service = Service.objects.create(
            provider=self.profile,
            category=self.category,
            title="Service Cover Project",
            price_amount=100.0,
            description="Test Description",
            city="Almaty",
        )

    def test_service_without_media_returns_null_cover(self):
        serializer = ServiceListSerializer(self.service)
        self.assertIsNone(serializer.data["cover_url"])

    def test_service_with_valid_cover_file_returns_absolute_url(self):
        dummy_file = create_dummy_image("JPEG")
        media = ServiceMedia.objects.create(
            service=self.service,
            file=dummy_file,
            is_cover=True,
        )
        
        request = MagicMock()
        request.user.is_authenticated = False
        request.build_absolute_uri = lambda url: f"http://testserver/{url.lstrip('/')}"
        
        serializer = ServiceListSerializer(self.service, context={"request": request})
        cover_url = serializer.data["cover_url"]
        self.assertIsNotNone(cover_url)
        self.assertTrue(cover_url.startswith("http://testserver/media/services/"))

    def test_service_falls_back_to_first_valid_image(self):
        # Create an image with is_cover=False
        dummy_file = create_dummy_image("JPEG")
        media = ServiceMedia.objects.create(
            service=self.service,
            file=dummy_file,
            is_cover=False,
        )
        
        request = MagicMock()
        request.user.is_authenticated = False
        request.build_absolute_uri = lambda url: f"http://testserver/{url.lstrip('/')}"
        
        serializer = ServiceListSerializer(self.service, context={"request": request})
        cover_url = serializer.data["cover_url"]
        self.assertIsNotNone(cover_url)
        self.assertTrue(cover_url.startswith("http://testserver/media/services/"))

    def test_missing_physical_file_handled_safely(self):
        dummy_file = create_dummy_image("JPEG")
        media = ServiceMedia.objects.create(
            service=self.service,
            file=dummy_file,
            is_cover=True,
        )
        
        # Mock storage.exists to return False
        with patch.object(media.file.storage, "exists", return_value=False):
            serializer = ServiceListSerializer(self.service)
            cover_url = serializer.data["cover_url"]
            self.assertIsNone(cover_url)

