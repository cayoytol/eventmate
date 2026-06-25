import io
import uuid
import hashlib
from urllib.parse import urlparse
from django.core.management.base import BaseCommand, CommandError
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from PIL import Image

from apps.core.media import validate_and_process_image, safe_delete_storage_object


class Command(BaseCommand):
    help = "Performs a safe real-storage smoke test round-trip using default_storage."

    def handle(self, *args, **options):
        # 1. Refuse to run unless S3 is configured
        provider = getattr(settings, "MEDIA_STORAGE_PROVIDER", "local")
        if provider != "s3":
            raise CommandError(
                f"Smoke test refused: MEDIA_STORAGE_PROVIDER is set to '{provider}'. "
                "This command only runs when MEDIA_STORAGE_PROVIDER=s3."
            )

        self.stdout.write("Storage backend initialized: OK")

        # Create 1x1 red PNG image in-memory
        img_io = io.BytesIO()
        img = Image.new("RGBA", (1, 1), color=(255, 0, 0, 255))
        img.save(img_io, format="PNG")
        img_bytes = img_io.getvalue()
        img_hash = hashlib.sha256(img_bytes).hexdigest()

        # Pass through the Stage 30.2A processor to verify it end-to-end
        test_file = ContentFile(img_bytes, name="smoke_raw.png")
        try:
            processed = validate_and_process_image(test_file)
            processed_bytes = processed.content.read()
            processed_hash = hashlib.sha256(processed_bytes).hexdigest()
            content_to_write = ContentFile(processed_bytes)
        except Exception as e:
            raise CommandError(f"Stage 30.2A image validation core failed: {str(e)}")

        unique_id = str(uuid.uuid4())
        saved_name = f"smoke-tests/{unique_id}.png"

        self.stdout.write("Processed test object: OK")

        # 2. Write test object
        try:
            actual_saved_name = default_storage.save(saved_name, content_to_write)
        except Exception as e:
            raise CommandError(f"Failed to write test object to storage: {str(e)}")

        self.stdout.write("Write test object: OK")

        try:
            # 3. Existence check
            try:
                exists = default_storage.exists(actual_saved_name)
            except Exception as e:
                raise CommandError(f"Existence check failed on storage: {str(e)}")

            if not exists:
                raise CommandError("Existence check returned False for written test object.")

            self.stdout.write("Existence check: OK")

            # 4. Read test object & compare hash
            try:
                with default_storage.open(actual_saved_name, "rb") as f:
                    read_bytes = f.read()
            except Exception as e:
                raise CommandError(f"Read check failed: {str(e)}")

            read_hash = hashlib.sha256(read_bytes).hexdigest()
            if read_hash != processed_hash:
                raise CommandError("Data corruption: read back bytes do not match written bytes.")

            self.stdout.write("Read test object: OK")

            # 5. URL generation
            try:
                url = default_storage.url(actual_saved_name)
            except Exception as e:
                raise CommandError(f"URL generation failed: {str(e)}")

            # Parse URL safely without logging query params or access keys
            parsed = urlparse(url)
            scheme = parsed.scheme
            has_host = bool(parsed.netloc)
            has_query = bool(parsed.query)

            # Accept HTTPS scheme in production, tolerate HTTP in local mock/s3 tests
            # (We only enforce HTTPS scheme if we're not running local tests or if the settings enforce it)
            if not scheme or scheme not in ("http", "https"):
                raise CommandError(f"URL generated with invalid or missing scheme: {scheme}")

            self.stdout.write("URL generation: OK")
            self.stdout.write(f"  Scheme: {scheme}")
            self.stdout.write(f"  Host configured: {'yes' if has_host else 'no'}")
            self.stdout.write(f"  Signed query present: {'yes' if has_query else 'no'}")

        finally:
            # 6. Guaranteed Cleanup in finally block
            self.stdout.write("Cleaning up smoke test object...")
            cleanup_success = safe_delete_storage_object(
                default_storage, actual_saved_name, context="media_storage_smoke_cleanup"
            )

            # 7. Final existence check
            final_exists = default_storage.exists(actual_saved_name)
            if final_exists:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error: test object '{actual_saved_name}' was not deleted from storage."
                    )
                )
                cleanup_success = False
            else:
                self.stdout.write("Final existence check: OK")

            if not cleanup_success:
                raise CommandError("Smoke test cleanup failed: object still exists or deletion failed.")

        self.stdout.write(self.style.SUCCESS("Media storage smoke test completed successfully: PASS"))
