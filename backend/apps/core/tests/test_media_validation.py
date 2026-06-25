import io
import warnings
from django.test import SimpleTestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from PIL import Image
from apps.core.media import (
    validate_and_process_image,
    generate_image_storage_name,
)


def create_dummy_image(format_name, size=(10, 10), color="blue", mode="RGB"):
    im = Image.new(mode, size, color)
    buf = io.BytesIO()
    im.save(buf, format=format_name)
    buf.seek(0)
    return SimpleUploadedFile(
        f"test.{format_name.lower()}",
        buf.read(),
        content_type=f"image/{format_name.lower()}",
    )


class MediaValidationTest(SimpleTestCase):
    def test_valid_jpeg_accepted(self):
        uploaded = create_dummy_image("JPEG")
        processed = validate_and_process_image(uploaded)
        self.assertEqual(processed.extension, "jpg")
        self.assertEqual(processed.mime_type, "image/jpeg")
        self.assertEqual(processed.width, 10)
        self.assertEqual(processed.height, 10)
        self.assertTrue(processed.size > 0)

    def test_valid_png_accepted(self):
        uploaded = create_dummy_image("PNG")
        processed = validate_and_process_image(uploaded)
        self.assertEqual(processed.extension, "png")
        self.assertEqual(processed.mime_type, "image/png")

    def test_valid_webp_accepted(self):
        from PIL import features

        if not features.check("webp"):
            self.skipTest("WebP not supported in current Pillow installation.")
        uploaded = create_dummy_image("WEBP")
        processed = validate_and_process_image(uploaded)
        self.assertEqual(processed.extension, "webp")
        self.assertEqual(processed.mime_type, "image/webp")

    def test_webp_unsupported_runtime_handled_safely(self):
        from unittest.mock import patch

        uploaded = create_dummy_image("WEBP")
        with patch("PIL.features.check", return_value=False):
            with self.assertRaises(ValidationError) as ctx:
                validate_and_process_image(uploaded)
            self.assertIn(
                "WebP support is not available", str(ctx.exception)
            )

    def test_empty_file_rejected(self):
        uploaded = SimpleUploadedFile("empty.jpg", b"", content_type="image/jpeg")
        with self.assertRaises(ValidationError) as ctx:
            validate_and_process_image(uploaded)
        self.assertIn("empty", str(ctx.exception))

    def test_missing_file_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_and_process_image(None)
        self.assertIn("No file was uploaded", str(ctx.exception))

    @override_settings(MEDIA_MAX_IMAGE_SIZE_MB=0.0001)  # ~100 bytes
    def test_file_over_size_rejected_before_decode(self):
        # Image will be larger than 100 bytes
        uploaded = create_dummy_image("JPEG", size=(50, 50))
        with self.assertRaises(ValidationError) as ctx:
            validate_and_process_image(uploaded)
        self.assertIn("exceeds the limit", str(ctx.exception))

    def test_svg_rejected(self):
        svg_content = b"<svg><rect width='10' height='10'/></svg>"
        uploaded = SimpleUploadedFile(
            "test.svg", svg_content, content_type="image/svg+xml"
        )
        with self.assertRaises(ValidationError):
            validate_and_process_image(uploaded)

    def test_gif_rejected(self):
        uploaded = create_dummy_image("GIF")
        with self.assertRaises(ValidationError) as ctx:
            validate_and_process_image(uploaded)
        self.assertIn("Unsupported image format: GIF", str(ctx.exception))

    def test_bmp_rejected(self):
        uploaded = create_dummy_image("BMP")
        with self.assertRaises(ValidationError):
            validate_and_process_image(uploaded)

    def test_corrupt_image_rejected(self):
        uploaded = SimpleUploadedFile(
            "corrupt.jpg", b"invalid-binary-content-here", content_type="image/jpeg"
        )
        with self.assertRaises(ValidationError):
            validate_and_process_image(uploaded)

    def test_text_renamed_to_jpg_rejected(self):
        uploaded = SimpleUploadedFile(
            "text.jpg", b"Just some plain text content", content_type="image/jpeg"
        )
        with self.assertRaises(ValidationError):
            validate_and_process_image(uploaded)

    def test_jpeg_renamed_to_png_accepted_and_normalized(self):
        # Create JPEG binary but name it PNG
        im = Image.new("RGB", (10, 10), "red")
        buf = io.BytesIO()
        im.save(buf, format="JPEG")
        buf.seek(0)
        uploaded = SimpleUploadedFile(
            "fake.png", buf.read(), content_type="image/png"
        )

        processed = validate_and_process_image(uploaded)
        self.assertEqual(processed.extension, "jpg")
        self.assertEqual(processed.mime_type, "image/jpeg")

    @override_settings(MEDIA_MAX_IMAGE_WIDTH=20, MEDIA_MAX_IMAGE_HEIGHT=20)
    def test_oversized_image_resized(self):
        uploaded = create_dummy_image("JPEG", size=(40, 20))
        processed = validate_and_process_image(uploaded)
        self.assertEqual(processed.width, 20)
        self.assertEqual(processed.height, 10)  # aspect ratio preserved

    @override_settings(MEDIA_MAX_IMAGE_WIDTH=200, MEDIA_MAX_IMAGE_HEIGHT=200)
    def test_small_image_not_upscaled(self):
        uploaded = create_dummy_image("JPEG", size=(50, 50))
        processed = validate_and_process_image(uploaded)
        self.assertEqual(processed.width, 50)
        self.assertEqual(processed.height, 50)

    def test_animated_gif_rejected(self):
        im1 = Image.new("RGB", (10, 10), "red")
        im2 = Image.new("RGB", (10, 10), "blue")
        buf = io.BytesIO()
        im1.save(buf, format="GIF", save_all=True, append_images=[im2])
        buf.seek(0)
        uploaded = SimpleUploadedFile(
            "animated.gif", buf.read(), content_type="image/gif"
        )
        with self.assertRaises(ValidationError):
            validate_and_process_image(uploaded)

    def test_exif_gps_metadata_removed(self):
        # Create JPEG with orientation EXIF metadata
        im = Image.new("RGB", (10, 10), "red")
        exif = im.getexif()
        exif[0x0112] = 6  # Rotate 90 CW
        buf = io.BytesIO()
        im.save(buf, format="JPEG", exif=exif)
        buf.seek(0)
        uploaded = SimpleUploadedFile(
            "exif.jpg", buf.read(), content_type="image/jpeg"
        )

        processed = validate_and_process_image(uploaded)
        out_img = Image.open(processed.content)
        # Verify EXIF dictionary is empty/non-existent
        self.assertEqual(len(out_img.getexif() or {}), 0)

    def test_uuid_storage_name_generation(self):
        path = generate_image_storage_name("avatars", 42, "jpg")
        parts = path.split("/")
        self.assertEqual(parts[0], "avatars")
        self.assertEqual(parts[1], "42")
        self.assertTrue(parts[2].endswith(".jpg"))
        self.assertEqual(len(parts[2].split(".")[0]), 36)  # UUID size

        # With resource ID
        path2 = generate_image_storage_name(
            "services", "provider-1", "png", "service-123"
        )
        parts2 = path2.split("/")
        self.assertEqual(parts2[0], "services")
        self.assertEqual(parts2[1], "provider-1")
        self.assertEqual(parts2[2], "service-123")
        self.assertTrue(parts2[3].endswith(".png"))

        # Path traversal block
        with self.assertRaises(ValueError):
            generate_image_storage_name("avatars", "../42", "jpg")

        with self.assertRaises(ValueError):
            generate_image_storage_name("avatars", "42", "jpg", "sub/folder")

    def test_decompression_bomb_warning_converted(self):
        original_max = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = 100
        try:
            # 11x11 = 121 pixels > 100 limit
            uploaded = create_dummy_image("JPEG", size=(11, 11))
            with self.assertRaises(ValidationError) as ctx:
                validate_and_process_image(uploaded)
            self.assertIn("Decompression bomb", str(ctx.exception))
        finally:
            Image.MAX_IMAGE_PIXELS = original_max

    @override_settings(MEDIA_MAX_SOURCE_IMAGE_PIXELS=100)
    def test_source_pixel_safety_limit(self):
        uploaded = create_dummy_image("JPEG", size=(11, 11))
        with self.assertRaises(ValidationError) as ctx:
            validate_and_process_image(uploaded)
        self.assertIn("exceed application safety limits", str(ctx.exception))

    @override_settings(MEDIA_MAX_IMAGE_SIZE_MB=0.000001)  # 1 byte limit
    def test_final_encoded_size_limit(self):
        # 50x50 image is larger than 1 byte when saved as PNG
        uploaded = create_dummy_image("PNG", size=(50, 50))
        with self.assertRaises(ValidationError) as ctx:
            validate_and_process_image(uploaded)
        self.assertIn("size exceeds", str(ctx.exception))

    def test_unexpected_file_pointer_position_handled(self):
        uploaded = create_dummy_image("JPEG")
        uploaded.seek(5)  # Offset pointer
        processed = validate_and_process_image(uploaded)
        self.assertEqual(processed.width, 10)

    def test_repeated_processing_succeeds(self):
        uploaded = create_dummy_image("JPEG")
        processed1 = validate_and_process_image(uploaded)
        processed2 = validate_and_process_image(uploaded)
        self.assertEqual(processed1.width, processed2.width)

    def test_build_absolute_media_url(self):
        from apps.core.media import build_absolute_media_url
        from unittest.mock import MagicMock
        
        # 1. Missing file -> None
        self.assertIsNone(build_absolute_media_url(None))
        self.assertIsNone(build_absolute_media_url(""))
        
        # 2. Storage URL starting with http:// or https:// -> return unchanged
        self.assertEqual(
            build_absolute_media_url("http://example.com/media/test.jpg"),
            "http://example.com/media/test.jpg"
        )
        self.assertEqual(
            build_absolute_media_url("https://example.com/media/test.jpg"),
            "https://example.com/media/test.jpg"
        )
        
        # Mocking a Django FileField/ImageField-like object
        class MockFile:
            def __init__(self, name, url):
                self.name = name
                self.url = url
            def __str__(self):
                return self.name
                
        file_absolute = MockFile("https://bucket.s3.amazonaws.com/media/pic.jpg", "https://bucket.s3.amazonaws.com/media/pic.jpg")
        self.assertEqual(
            build_absolute_media_url(file_absolute),
            "https://bucket.s3.amazonaws.com/media/pic.jpg"
        )
        
        # 3. Relative storage URL with request -> request.build_absolute_uri(url)
        request = MagicMock()
        request.build_absolute_uri.return_value = "http://testserver/media/avatars/user_1/avatar.jpg"
        
        file_relative = MockFile("avatars/user_1/avatar.jpg", "/media/avatars/user_1/avatar.jpg")
        self.assertEqual(
            build_absolute_media_url(file_relative, request),
            "http://testserver/media/avatars/user_1/avatar.jpg"
        )
        request.build_absolute_uri.assert_called_once_with("/media/avatars/user_1/avatar.jpg")
        
        # 4. Relative storage URL without request -> combine with PUBLIC_BACKEND_URL
        with override_settings(PUBLIC_BACKEND_URL="https://sfera-backend-8hif.onrender.com"):
            self.assertEqual(
                build_absolute_media_url(file_relative),
                "https://sfera-backend-8hif.onrender.com/media/avatars/user_1/avatar.jpg"
            )
            
        with override_settings(PUBLIC_BACKEND_URL="https://sfera-backend-8hif.onrender.com/"):
            self.assertEqual(
                build_absolute_media_url(file_relative),
                "https://sfera-backend-8hif.onrender.com/media/avatars/user_1/avatar.jpg"
            )

