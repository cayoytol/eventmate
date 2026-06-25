import os
import shutil
import tempfile
import io
import hashlib
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage, storages, FileSystemStorage
from django.utils.functional import empty

from apps.accounts.models import ProviderProfile
from apps.catalog.models import Category, Service, ServiceMedia
from apps.portfolio.models import PortfolioItem, PortfolioMedia

User = get_user_model()


class MediaCommandsTestCase(TestCase):
    def setUp(self):
        # Create a temporary directory for local storage checks
        self.temp_dir = tempfile.mkdtemp()
        
        # Manually assign overridden default storage
        self.temp_storage = FileSystemStorage(location=self.temp_dir)
        
        # Save old wrapped storages for restoration
        self.old_wrapped = getattr(default_storage, "_wrapped", empty)
        self.old_storages_default = storages._storages.get("default")
        
        storages._storages["default"] = self.temp_storage
        default_storage._wrapped = self.temp_storage
        
        # Create test users and structures
        self.user = User.objects.create_user(
            email="provider@example.com",
            username="provider",
            password="Password123!",
            role="provider"
        )
        self.provider_profile, _ = ProviderProfile.objects.get_or_create(user=self.user)
        self.category = Category.objects.create(name_ru="Тест", slug="test")
        self.service = Service.objects.create(
            provider=self.provider_profile,
            category=self.category,
            title="Тест услуга",
            description="Описание услуги",
            price_amount=1500
        )
        self.portfolio_item = PortfolioItem.objects.create(
            provider_profile=self.provider_profile,
            title="Портфолио элемент"
        )

    def tearDown(self):
        # Restore old wrapped storage
        if self.old_wrapped is empty:
            default_storage._wrapped = empty
        else:
            default_storage._wrapped = self.old_wrapped
            
        if self.old_storages_default is None:
            if "default" in storages._storages:
                del storages._storages["default"]
        else:
            storages._storages["default"] = self.old_storages_default

        # Clean up local temporary storage directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def write_temp_file(self, path, content=b"fake_data"):
        full_path = os.path.join(self.temp_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(content)
        return path

    def test_audit_media_clean_state(self):
        """1. Clean database state has zero audit issues."""
        out = io.StringIO()
        call_command("audit_media_storage", stdout=out)
        output = out.getvalue()
        
        self.assertIn("Referenced objects: 0", output)
        self.assertIn("Existing objects: 0", output)
        self.assertIn("Missing objects: 0", output)

    def test_audit_media_clean_referenced(self):
        """1 (continued). Clean referenced objects."""
        # Create user avatar on storage
        avatar_path = f"avatars/{self.user.pk}/avatar.jpg"
        self.write_temp_file(avatar_path)
        self.user.avatar.name = avatar_path
        self.user.save()

        # Create Category icon
        icon_path = "categories/cat.png"
        self.write_temp_file(icon_path)
        self.category.icon.name = icon_path
        self.category.save()

        out = io.StringIO()
        call_command("audit_media_storage", stdout=out)
        output = out.getvalue()
        
        self.assertIn("Referenced objects: 2", output)
        self.assertIn("Existing objects: 2", output)
        self.assertIn("Missing objects: 0", output)

    def test_audit_media_missing_object(self):
        """2. Missing referenced object."""
        self.user.avatar.name = f"avatars/{self.user.pk}/missing_avatar.jpg"
        self.user.save()

        out = io.StringIO()
        call_command("audit_media_storage", stdout=out)
        output = out.getvalue()
        
        self.assertIn("Referenced objects: 1", output)
        self.assertIn("Existing objects: 0", output)
        self.assertIn("Missing objects: 1", output)

    def test_audit_media_duplicate_exact_reference(self):
        """3. Duplicate exact reference (same file used by multiple records)."""
        dup_path = "categories/shared.png"
        self.write_temp_file(dup_path)

        # Set same icon for two categories
        self.category.icon.name = dup_path
        self.category.save()

        category2 = Category.objects.create(name_ru="Тест 2", slug="test2")
        category2.icon.name = dup_path
        category2.save()

        out = io.StringIO()
        call_command("audit_media_storage", stdout=out)
        output = out.getvalue()
        
        self.assertIn("Referenced objects: 2", output)
        self.assertIn("Existing objects: 1", output)
        self.assertIn("Duplicate references: 1", output)

    def test_audit_media_unsafe_leading_slash(self):
        """4. Unsafe leading slash check."""
        self.user.avatar.name = "/avatars/1/avatar.jpg"
        self.user.save()

        out = io.StringIO()
        call_command("audit_media_storage", stdout=out)
        output = out.getvalue()
        
        self.assertIn("Unsafe paths: 1", output)

    def test_audit_media_unsafe_traversal(self):
        """5. Unsafe .. traversal path check."""
        self.user.avatar.name = "avatars/1/../../etc/passwd"
        self.user.save()

        out = io.StringIO()
        call_command("audit_media_storage", stdout=out)
        output = out.getvalue()
        
        self.assertIn("Unsafe paths: 1", output)

    def test_audit_media_unsafe_backslash(self):
        """6. Unsafe backslash path check."""
        self.user.avatar.name = "avatars\\1\\avatar.jpg"
        self.user.save()

        out = io.StringIO()
        call_command("audit_media_storage", stdout=out)
        output = out.getvalue()
        
        self.assertIn("Unsafe paths: 1", output)

    def test_audit_media_ownership_folder_mismatch(self):
        """7. Ownership folder mismatch checks."""
        # WRONG owner user ID
        self.user.avatar.name = "avatars/999/avatar.jpg"
        self.user.save()

        out = io.StringIO()
        call_command("audit_media_storage", stdout=out)
        output = out.getvalue()
        
        self.assertIn("Ownership-path mismatches: 1", output)

    def test_audit_media_orphans_under_managed_prefixes(self):
        """8-10. Orphan files under avatars/, services/, portfolio/."""
        # Write orphan files
        self.write_temp_file("avatars/1/orphan.jpg")
        self.write_temp_file("services/1/2/orphan.jpg")
        self.write_temp_file("portfolio/1/3/orphan.jpg")

        out = io.StringIO()
        call_command("audit_media_storage", "--scan-orphans", stdout=out)
        output = out.getvalue()
        
        self.assertIn("Orphans detected: 3", output)
        self.assertIn("avatars/*/orphan.jpg", output)
        self.assertIn("services/*/*/orphan.jpg", output)
        self.assertIn("portfolio/*/*/orphan.jpg", output)

    def test_audit_media_category_orphan_is_report_only(self):
        """11. Category orphan is report-only (no deletion under categories/)."""
        self.write_temp_file("categories/orphan_cat.png")

        out = io.StringIO()
        # Attempt to delete orphans, but categories/ must not be deleted
        call_command(
            "audit_media_storage",
            "--scan-orphans",
            "--delete-orphans",
            "--confirm-delete-orphans",
            stdout=out
        )
        output = out.getvalue()
        
        self.assertIn("Orphans detected: 1", output)
        # Verify it remains report-only, deletion count is 0
        self.assertIn("Orphans deleted: 0", output)
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "categories/orphan_cat.png")))

    def test_audit_media_default_mode_does_not_list(self):
        """12. Default mode does not list storage orphans."""
        self.write_temp_file("avatars/1/orphan.jpg")

        out = io.StringIO()
        call_command("audit_media_storage", stdout=out)
        output = out.getvalue()
        
        self.assertNotIn("Orphans detected", output)

    def test_audit_media_dry_run_deletes_nothing(self):
        """13. Dry-run does not delete orphans."""
        self.write_temp_file("avatars/1/orphan.jpg")

        out = io.StringIO()
        # Scan but do not delete
        call_command("audit_media_storage", "--scan-orphans", stdout=out)
        output = out.getvalue()
        
        self.assertIn("Orphans detected: 1", output)
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "avatars/1/orphan.jpg")))

    def test_audit_media_strict_mode_fails(self):
        """14. Strict mode fails on issues."""
        self.user.avatar.name = f"avatars/{self.user.pk}/missing.jpg"
        self.user.save()

        with self.assertRaises(CommandError):
            call_command("audit_media_storage", "--strict", stdout=io.StringIO())

    def test_audit_media_strict_mode_succeeds_when_clean(self):
        """15. Clean strict mode succeeds."""
        avatar_path = f"avatars/{self.user.pk}/avatar.jpg"
        self.write_temp_file(avatar_path)
        self.user.avatar.name = avatar_path
        self.user.save()

        out = io.StringIO()
        call_command("audit_media_storage", "--strict", stdout=out)
        self.assertIn("Audit Summary", out.getvalue())

    def test_audit_media_scan_restricted_prefixes(self):
        """16. Scan is restricted to managed prefixes."""
        # Unrelated path should be ignored
        self.write_temp_file("unrelated/file.jpg")
        self.write_temp_file("avatars/1/orphan.jpg")

        out = io.StringIO()
        call_command("audit_media_storage", "--scan-orphans", "--prefix", "avatars", stdout=out)
        output = out.getvalue()
        
        self.assertIn("Orphans detected: 1", output)
        self.assertNotIn("unrelated/file.jpg", output)

    def test_audit_media_max_objects_limit(self):
        """18-19. max-objects stops scan safely & reports incomplete."""
        self.write_temp_file("avatars/1/orphan1.jpg")
        self.write_temp_file("avatars/1/orphan2.jpg")
        self.write_temp_file("avatars/1/orphan3.jpg")

        out = io.StringIO()
        call_command("audit_media_storage", "--scan-orphans", "--max-objects", "2", stdout=out)
        output = out.getvalue()
        
        self.assertIn("Scan limit reached. Scan is incomplete.", output)

    def test_audit_media_delete_orphans_flags_validation(self):
        """20-21. Delete requires scan and confirmation flags."""
        with self.assertRaises(CommandError):
            call_command("audit_media_storage", "--delete-orphans")
            
        with self.assertRaises(CommandError):
            call_command("audit_media_storage", "--confirm-delete-orphans")

    def test_audit_media_exact_orphan_deletion_succeeds(self):
        """22-24. Exact orphan deletion succeeds and never deletes prefix or referenced files."""
        # Referenced file
        ref_path = f"avatars/{self.user.pk}/avatar.jpg"
        self.write_temp_file(ref_path)
        self.user.avatar.name = ref_path
        self.user.save()

        # Orphan file
        orphan_path = "avatars/1/orphan.jpg"
        self.write_temp_file(orphan_path)

        out = io.StringIO()
        call_command(
            "audit_media_storage",
            "--scan-orphans",
            "--delete-orphans",
            "--confirm-delete-orphans",
            stdout=out
        )
        output = out.getvalue()

        self.assertIn("Orphans deleted: 1", output)
        # Orphan deleted
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir, orphan_path)))
        # Referenced kept
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, ref_path)))


class MediaStorageSmokeTestCase(TestCase):
    def setUp(self):
        # Local mock settings
        pass

    @override_settings(MEDIA_STORAGE_PROVIDER="local")
    def test_smoke_refused_on_local_provider(self):
        """1. Local provider is refused."""
        with self.assertRaises(CommandError) as ctx:
            call_command("media_storage_smoke")
        self.assertIn("only runs when MEDIA_STORAGE_PROVIDER=s3", str(ctx.exception))

    @override_settings(MEDIA_STORAGE_PROVIDER="s3")
    def test_smoke_command_execution_success(self):
        """2-11. S3-configured smoke proceeds and round-trips correctly under mock context."""
        # Mock default_storage write/read/exists/url/delete operations
        # Create a dummy class that inherits from Storage
        from django.core.files.storage import Storage
        
        class MockS3Storage(Storage):
            def __init__(self):
                self.files = {}
                
            def _save(self, name, content):
                self.files[name] = content.read()
                return name
                
            def exists(self, name):
                return name in self.files
                
            def open(self, name, mode="rb"):
                return io.BytesIO(self.files[name])
                
            def url(self, name):
                return f"https://mock-bucket.s3.amazonaws.com/{name}?Signature=mock"
                
            def delete(self, name):
                if name in self.files:
                    del self.files[name]

        mock_storage = MockS3Storage()
        
        with patch("apps.core.management.commands.media_storage_smoke.default_storage", mock_storage):
            out = io.StringIO()
            call_command("media_storage_smoke", stdout=out)
            output = out.getvalue()
            
            self.assertIn("Storage backend initialized: OK", output)
            self.assertIn("Write test object: OK", output)
            self.assertIn("Existence check: OK", output)
            self.assertIn("Read test object: OK", output)
            self.assertIn("URL generation: OK", output)
            self.assertIn("Final existence check: OK", output)
            self.assertIn("Media storage smoke test completed successfully: PASS", output)
            
            # Privacy requirements: Full signed URL is not printed, only metadata parsed
            self.assertNotIn("mock-bucket.s3.amazonaws.com", output)
            self.assertNotIn("Signature=mock", output)

    @override_settings(MEDIA_STORAGE_PROVIDER="s3")
    def test_smoke_failure_handling(self):
        """12-15. Smoke fails when write, read or delete operations fail."""
        from django.core.files.storage import Storage

        class BrokenS3Storage(Storage):
            def _save(self, name, content):
                raise IOError("Write failed")

        mock_storage = BrokenS3Storage()

        with patch("apps.core.management.commands.media_storage_smoke.default_storage", mock_storage):
            with self.assertRaises(CommandError) as ctx:
                call_command("media_storage_smoke", stdout=io.StringIO())
            self.assertIn("Failed to write test object", str(ctx.exception))
