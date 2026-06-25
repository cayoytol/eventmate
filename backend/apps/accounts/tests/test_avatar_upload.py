import io
import uuid
import logging
from unittest.mock import patch
from django.test import override_settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase, APIRequestFactory
from PIL import Image
from apps.accounts.serializers import UserSerializer, ProviderPublicProfileSerializer
from apps.catalog.serializers import ProviderProfileMinSerializer
from apps.favorites.serializers import FavoriteListSerializer
from apps.favorites.models import Favorite
from apps.accounts.models import ProviderProfile

User = get_user_model()


def create_test_image(img_format="JPEG", size=(1, 1)):
    file = io.BytesIO()
    image = Image.new('RGB', size, color='white')
    image.save(file, format=img_format)
    file.name = f'test.{img_format.lower()}'
    file.seek(0)
    return file

_TEST_LOCAL_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


@override_settings(STORAGES=_TEST_LOCAL_STORAGES)
class UserAvatarUploadAPITest(APITestCase):
    def setUp(self):
        # Clear cache/throttling state between runs
        cache.clear()

        # Create provider
        self.provider_user = User.objects.create_user(
            email="provider@example.com",
            username="provider1",
            password="Password123!",
            role="provider"
        )
        self.provider_profile, _ = ProviderProfile.objects.get_or_create(user=self.provider_user)

        # Create client
        self.client_user = User.objects.create_user(
            email="client@example.com",
            username="client1",
            password="Password123!",
            role="client"
        )

        self.url = reverse("profile_me_avatar_alias")
        self.factory = APIRequestFactory()

    def tearDown(self):
        cache.clear()
        # Clean up any leftover test files in default_storage
        try:
            if self.provider_user.avatar and self.provider_user.avatar.name:
                self.provider_user.avatar.storage.delete(self.provider_user.avatar.name)
        except Exception:
            pass

    def test_user_without_avatar_remains_valid(self):
        self.assertFalse(self.provider_user.avatar.name)
        self.assertTrue(self.provider_user.is_active)

    def test_existing_avatar_field_remains_compatible(self):
        self.provider_user.avatar = "avatars/1/custom.jpg"
        self.provider_user.save()
        user = User.objects.get(pk=self.provider_user.pk)
        self.assertEqual(user.avatar.name, "avatars/1/custom.jpg")

    def test_provider_uploads_jpeg(self):
        self.client.force_authenticate(user=self.provider_user)
        img_file = create_test_image("JPEG")
        response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("avatar_url", response.data)
        self.provider_user.refresh_from_db()
        self.assertTrue(self.provider_user.avatar.name.startswith("avatars/"))
        self.assertTrue(self.provider_user.avatar.name.endswith(".jpg"))

    def test_provider_uploads_png(self):
        self.client.force_authenticate(user=self.provider_user)
        img_file = create_test_image("PNG")
        response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.provider_user.refresh_from_db()
        self.assertTrue(self.provider_user.avatar.name.endswith(".png"))

    def test_provider_uploads_webp(self):
        self.client.force_authenticate(user=self.provider_user)
        img_file = create_test_image("WEBP")
        response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.provider_user.refresh_from_db()
        self.assertTrue(self.provider_user.avatar.name.endswith(".webp"))

    def test_anonymous_upload_rejected(self):
        img_file = create_test_image("JPEG")
        response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_client_upload_rejected(self):
        self.client.force_authenticate(user=self.client_user)
        img_file = create_test_image("JPEG")
        response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_avatar_rejected(self):
        self.client.force_authenticate(user=self.provider_user)
        response = self.client.post(self.url, {}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_svg_rejected(self):
        self.client.force_authenticate(user=self.provider_user)
        img_file = create_test_image("JPEG")
        with patch('apps.core.media.validate_and_process_image', side_effect=ValidationError("SVG")):
            response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_gif_rejected(self):
        self.client.force_authenticate(user=self.provider_user)
        img_file = create_test_image("JPEG")
        with patch('apps.core.media.validate_and_process_image', side_effect=ValidationError("GIF")):
            response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_corrupt_image_rejected(self):
        self.client.force_authenticate(user=self.provider_user)
        img_file = create_test_image("JPEG")
        with patch('apps.core.media.validate_and_process_image', side_effect=ValidationError("Corrupt")):
            response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_oversized_image_rejected(self):
        self.client.force_authenticate(user=self.provider_user)
        img_file = create_test_image("JPEG")
        with patch('apps.core.media.validate_and_process_image', side_effect=ValidationError("Oversized")):
            response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_safe_oversized_image_resized(self):
        self.client.force_authenticate(user=self.provider_user)
        img_file = create_test_image("JPEG", size=(5000, 100))
        # Ensure max source image width config allows it but resizes
        response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check that it resized down
        self.provider_user.refresh_from_db()
        img = Image.open(self.provider_user.avatar)
        self.assertLessEqual(img.width, 4096)

    def test_uuid_ownership_path_used(self):
        self.client.force_authenticate(user=self.provider_user)
        img_file = create_test_image("JPEG")
        response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.provider_user.refresh_from_db()
        # avatars/{user_id}/{uuid}.jpg
        path_parts = self.provider_user.avatar.name.split("/")
        self.assertEqual(path_parts[0], "avatars")
        self.assertEqual(path_parts[1], str(self.provider_user.pk))
        uuid_part = path_parts[2].split(".")[0]
        self.assertTrue(uuid.UUID(uuid_part))

    def test_original_filename_absent(self):
        self.client.force_authenticate(user=self.provider_user)
        img_file = create_test_image("JPEG")
        img_file.name = "very_secret_filename_should_not_leak.jpg"
        response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.provider_user.refresh_from_db()
        self.assertNotIn("very_secret_filename_should_not_leak", self.provider_user.avatar.name)

    def test_decoded_format_determines_extension(self):
        self.client.force_authenticate(user=self.provider_user)
        img_file = create_test_image("JPEG")
        img_file.name = "test.png"  # Mismatch extension in request filename
        response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.provider_user.refresh_from_db()
        self.assertTrue(self.provider_user.avatar.name.endswith(".jpg"))  # Determined by processed format

    def test_avatar_url_returned(self):
        self.client.force_authenticate(user=self.provider_user)
        img_file = create_test_image("JPEG")
        response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("avatar_url", response.data)
        self.assertIsNotNone(response.data["avatar_url"])

    def test_storage_internals_absent(self):
        """Avatar response must not leak any S3/AWS/bucket/secret internals"""
        self.client.force_authenticate(user=self.provider_user)
        img_file = create_test_image("JPEG")
        response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Under local storage: no AWS details should appear in response
        response_str = str(response.data)
        self.assertNotIn("bucket", response_str.lower())
        self.assertNotIn("secret", response_str.lower())

    def test_post_uses_media_upload_throttle(self):
        # Reset cache first to ensure a clean throttle state for this test
        cache.clear()
        self.client.force_authenticate(user=self.provider_user)
        img_file = create_test_image("JPEG")
        
        # Trigger rate limit
        throttled = False
        for _ in range(15):
            img_file.seek(0)
            response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                throttled = True
                break
        self.assertTrue(throttled)

    def test_replacement_deletes_old_after_commit(self):
        self.client.force_authenticate(user=self.provider_user)
        storage = self.provider_user.avatar.storage
        
        saved_old = storage.save("avatars/1/old.jpg", ContentFile(b"old-data"))
        self.provider_user.avatar.name = saved_old
        self.provider_user.save()

        img_file = create_test_image("PNG")
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertFalse(storage.exists(saved_old))
        self.provider_user.refresh_from_db()
        self.assertTrue(storage.exists(self.provider_user.avatar.name))

    def test_failed_processing_preserves_old_avatar(self):
        self.client.force_authenticate(user=self.provider_user)
        storage = self.provider_user.avatar.storage
        saved_old = storage.save("avatars/1/old.jpg", ContentFile(b"old-data"))
        self.provider_user.avatar.name = saved_old
        self.provider_user.save()

        # Send corrupt file (failed processing)
        img_file = create_test_image("JPEG")
        with patch('apps.core.media.validate_and_process_image', side_effect=ValidationError("Corrupt")):
            response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.provider_user.refresh_from_db()
        self.assertEqual(self.provider_user.avatar.name, saved_old)
        self.assertTrue(storage.exists(saved_old))

    def test_storage_save_failure_preserves_old_avatar(self):
        self.client.force_authenticate(user=self.provider_user)
        storage = self.provider_user.avatar.storage
        saved_old = storage.save("avatars/1/old.jpg", ContentFile(b"old-data"))
        self.provider_user.avatar.name = saved_old
        self.provider_user.save()

        img_file = create_test_image("JPEG")
        with patch.object(storage, 'save', side_effect=Exception("Storage write error")):
            response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        self.provider_user.refresh_from_db()
        self.assertEqual(self.provider_user.avatar.name, saved_old)
        self.assertTrue(storage.exists(saved_old))

    def test_db_failure_cleans_new_object(self):
        self.client.force_authenticate(user=self.provider_user)
        img_file = create_test_image("JPEG")
        
        with patch.object(User, 'save', side_effect=Exception("Database error")):
            response = self.client.post(self.url, {"avatar": img_file}, format="multipart")
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Confirm newly written storage file is cleaned up
        self.provider_user.refresh_from_db()
        self.assertFalse(self.provider_user.avatar.name)

    @patch('apps.accounts.views.safe_delete_image')
    def test_provider_removes_avatar(self, mock_delete):
        self.client.force_authenticate(user=self.provider_user)
        storage = self.provider_user.avatar.storage
        saved_old = storage.save("avatars/1/old.jpg", ContentFile(b"old-data"))
        self.provider_user.avatar.name = saved_old
        self.provider_user.save()

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(self.url)
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.provider_user.refresh_from_db()
        self.assertFalse(self.provider_user.avatar.name)
        mock_delete.assert_called_once_with(storage, saved_old)

    def test_removing_absent_avatar_returns_204(self):
        self.client.force_authenticate(user=self.provider_user)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_missing_storage_object_does_not_return_500(self):
        self.client.force_authenticate(user=self.provider_user)
        self.provider_user.avatar.name = "avatars/1/nonexistent.jpg"
        self.provider_user.save()

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(self.url)
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.provider_user.refresh_from_db()
        self.assertFalse(self.provider_user.avatar.name)

    def test_unrelated_user_fields_stay_unchanged(self):
        self.client.force_authenticate(user=self.provider_user)
        self.provider_user.username = "custom_username"
        self.provider_user.save()

        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.provider_user.refresh_from_db()
        self.assertEqual(self.provider_user.username, "custom_username")

    def test_delete_not_blocked_by_upload_throttle(self):
        self.client.force_authenticate(user=self.provider_user)
        # Trigger some uploads to consume throttle
        img_file = create_test_image("JPEG")
        for _ in range(5):
            img_file.seek(0)
            self.client.post(self.url, {"avatar": img_file}, format="multipart")
            
        # Delete must succeed without 429
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    @patch('apps.accounts.signals.safe_delete_storage_object')
    def test_user_deletion_schedules_avatar_cleanup(self, mock_delete):
        storage = self.provider_user.avatar.storage
        saved_old = storage.save("avatars/1/deleted_user.jpg", ContentFile(b"deleted-data"))
        self.provider_user.avatar.name = saved_old
        self.provider_user.save()

        with self.captureOnCommitCallbacks(execute=True):
            self.provider_user.delete()

        mock_delete.assert_called_once_with(storage, saved_old, context="user_avatar_post_delete")

    def test_relative_local_url_becomes_absolute_with_request(self):
        self.provider_user.avatar.name = "avatars/1/test.jpg"
        self.provider_user.save()

        request = self.factory.get("/")
        serializer = UserSerializer(self.provider_user, context={"request": request})
        self.assertEqual(serializer.data["avatar_url"], "http://testserver/media/avatars/1/test.jpg")

    def test_absolute_url_remains_unchanged(self):
        self.provider_user.avatar.name = "http://s3.amazonaws.com/bucket/avatars/1/test.jpg"
        self.provider_user.save()

        request = self.factory.get("/")
        serializer = UserSerializer(self.provider_user, context={"request": request})
        self.assertEqual(serializer.data["avatar_url"], "http://s3.amazonaws.com/bucket/avatars/1/test.jpg")

    def test_missing_avatar_resolves_safely_to_null(self):
        self.provider_user.avatar.name = None
        self.provider_user.save()

        request = self.factory.get("/")
        serializer = UserSerializer(self.provider_user, context={"request": request})
        self.assertIsNone(serializer.data["avatar_url"])

    def test_payload_user_id_is_ignored(self):
        self.client.force_authenticate(user=self.provider_user)
        img_file = create_test_image("JPEG")
        # Try to specify another user ID in payload
        response = self.client.post(self.url, {"avatar": img_file, "user_id": 9999, "role": "admin"}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.provider_user.refresh_from_db()
        # Target remains request.user
        self.assertEqual(self.provider_user.role, "provider")

    def test_normal_json_profile_patch_cannot_modify_avatar(self):
        self.client.force_authenticate(user=self.provider_user)
        self.provider_user.avatar.name = "avatars/1/original.jpg"
        self.provider_user.save()

        # Normal profile PATCH try to bypass and overwrite avatar
        response = self.client.patch(reverse("profile_me"), {"username": "newname", "avatar": "bypassed.jpg"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.provider_user.refresh_from_db()
        self.assertEqual(self.provider_user.avatar.name, "avatars/1/original.jpg")

    def test_normal_metadata_update_preserves_avatar(self):
        self.client.force_authenticate(user=self.provider_user)
        self.provider_user.avatar.name = "avatars/1/original.jpg"
        self.provider_user.save()

        response = self.client.patch(reverse("profile_me"), {"username": "newname"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.provider_user.refresh_from_db()
        self.assertEqual(self.provider_user.avatar.name, "avatars/1/original.jpg")

    def test_serializers_have_avatar_url(self):
        # UserSerializer
        self.provider_user.avatar.name = "avatars/1/test.jpg"
        self.provider_user.save()
        
        request = self.factory.get("/")
        request.user = self.provider_user

        user_serializer = UserSerializer(self.provider_user, context={"request": request})
        self.assertIn("avatar_url", user_serializer.data)
        
        # ProviderPublicProfileSerializer
        profile_serializer = ProviderPublicProfileSerializer(self.provider_profile, context={"request": request})
        self.assertIn("avatar_url", profile_serializer.data)

        # ProviderProfileMinSerializer
        min_serializer = ProviderProfileMinSerializer(self.provider_profile, context={"request": request})
        self.assertIn("avatar_url", min_serializer.data)

        # FavoriteListSerializer
        favorite = Favorite.objects.create(
            user=self.client_user,
            content_type=Favorite.ContentType.PROVIDER,
            object_id=self.provider_profile.id
        )
        fav_serializer = FavoriteListSerializer(favorite, context={"request": request})
        self.assertIn("avatar_url", fav_serializer.data["object_data"])
