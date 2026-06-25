from django.test import SimpleTestCase, override_settings
from django.core.exceptions import ImproperlyConfigured
from django.core.checks import Error, Warning as CheckWarning
from apps.core.storage import build_media_storages_config
from apps.core.checks import check_media_settings


class StorageConfigTest(SimpleTestCase):
    def test_local_mode_config(self):
        config = build_media_storages_config(
            provider="local",
            media_root="/media-root",
            media_url="/media-url/",
        )
        self.assertEqual(
            config["default"]["BACKEND"],
            "django.core.files.storage.FileSystemStorage",
        )
        self.assertEqual(config["default"]["OPTIONS"]["location"], "/media-root")
        self.assertEqual(config["default"]["OPTIONS"]["base_url"], "/media-url/")
        self.assertEqual(
            config["staticfiles"]["BACKEND"],
            "django.contrib.staticfiles.storage.StaticFilesStorage",
        )

    def test_s3_mode_config(self):
        config = build_media_storages_config(
            provider="s3",
            media_root="/media-root",
            media_url="/media-url/",
            access_key="my-key",
            secret_key="my-secret",
            bucket_name="my-bucket",
            endpoint_url="https://r2-endpoint",
            region_name="auto",
            custom_domain="my-cdn.com",
            querystring_auth=False,
            addressing_style="path",
            signature_version="s3v4",
        )
        self.assertEqual(
            config["default"]["BACKEND"], "storages.backends.s3.S3Storage"
        )
        opts = config["default"]["OPTIONS"]
        self.assertEqual(opts["access_key"], "my-key")
        self.assertEqual(opts["secret_key"], "my-secret")
        self.assertEqual(opts["bucket_name"], "my-bucket")
        self.assertEqual(opts["endpoint_url"], "https://r2-endpoint")
        self.assertEqual(opts["region_name"], "auto")
        self.assertEqual(opts["custom_domain"], "my-cdn.com")
        self.assertFalse(opts["querystring_auth"])
        self.assertEqual(opts["addressing_style"], "path")
        self.assertEqual(opts["signature_version"], "s3v4")
        self.assertIsNone(opts["default_acl"])
        self.assertFalse(opts["file_overwrite"])

    def test_s3_empty_optional_omitted(self):
        config = build_media_storages_config(
            provider="s3",
            media_root="/media-root",
            media_url="/media-url/",
            access_key="my-key",
            secret_key="my-secret",
            bucket_name="my-bucket",
            endpoint_url="",
            region_name=" ",
            custom_domain=None,
        )
        opts = config["default"]["OPTIONS"]
        self.assertNotIn("endpoint_url", opts)
        self.assertNotIn("region_name", opts)
        self.assertNotIn("custom_domain", opts)

    def test_unknown_provider_fails(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            build_media_storages_config(
                provider="invalid-provider",
                media_root="/media-root",
                media_url="/media-url/",
            )
        self.assertIn("Unsupported MEDIA_STORAGE_PROVIDER", str(ctx.exception))
        # Ensure secret value is not printed/logged
        self.assertNotIn("invalid-provider", str(ctx.exception))

    def test_missing_s3_bucket_fails(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            build_media_storages_config(
                provider="s3",
                media_root="/media-root",
                media_url="/media-url/",
                access_key="my-key",
                secret_key="my-secret",
                bucket_name="",
            )
        self.assertIn("Unsupported MEDIA_STORAGE_PROVIDER", str(ctx.exception))

    def test_missing_s3_credentials_fails(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            build_media_storages_config(
                provider="s3",
                media_root="/media-root",
                media_url="/media-url/",
                access_key="",
                secret_key="my-secret",
                bucket_name="my-bucket",
            )
        self.assertIn("Unsupported MEDIA_STORAGE_PROVIDER", str(ctx.exception))

    @override_settings(MEDIA_STORAGE_PROVIDER="invalid-provider")
    def test_system_check_unknown_provider(self):
        errors = check_media_settings(None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "media.E001")
        self.assertIsInstance(errors[0], Error)

    @override_settings(
        MEDIA_STORAGE_PROVIDER="s3",
        AWS_STORAGE_BUCKET_NAME="",
        AWS_ACCESS_KEY_ID="some-key",
        AWS_SECRET_ACCESS_KEY="some-secret",
    )
    def test_system_check_missing_bucket(self):
        errors = check_media_settings(None)
        self.assertTrue(any(e.id == "media.E002" for e in errors))

    @override_settings(
        MEDIA_STORAGE_PROVIDER="s3",
        AWS_STORAGE_BUCKET_NAME="some-bucket",
        AWS_ACCESS_KEY_ID="",
        AWS_SECRET_ACCESS_KEY="some-secret",
    )
    def test_system_check_missing_credentials(self):
        errors = check_media_settings(None)
        self.assertTrue(any(e.id == "media.E003" for e in errors))

    @override_settings(
        MEDIA_MAX_IMAGE_SIZE_MB=-1.0,
    )
    def test_system_check_invalid_limits(self):
        errors = check_media_settings(None)
        self.assertTrue(any(e.id == "media.E004" for e in errors))

    @override_settings(
        MEDIA_ALLOWED_IMAGE_TYPES=["image/webp"],
    )
    def test_system_check_webp_unsupported(self):
        from unittest.mock import patch

        with patch("PIL.features.check", return_value=False):
            errors = check_media_settings(None)
            self.assertTrue(any(e.id == "media.E005" for e in errors))
