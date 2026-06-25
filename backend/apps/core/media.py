import io
import re
import uuid
import warnings
from dataclasses import dataclass
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_PREFIXES = ("avatars", "services", "portfolio")


@dataclass(frozen=True)
class ProcessedImage:
    content: ContentFile
    extension: str
    mime_type: str
    width: int
    height: int
    size: int


def validate_and_process_image(uploaded_file) -> ProcessedImage:
    """
    Validates, decodes, normalizes, resizes, strips metadata, and re-encodes
    uploaded images. Returns a ProcessedImage object containing the ContentFile.
    Does not save to a database or storage.
    """
    if uploaded_file is None:
        raise ValidationError("No file was uploaded.")

    # 1. Size checks before expensive decoding
    size = getattr(uploaded_file, "size", None)
    if size is None or size <= 0:
        raise ValidationError("Uploaded file is empty.")

    max_size_mb = getattr(settings, "MEDIA_MAX_IMAGE_SIZE_MB", 5)
    max_size_bytes = int(max_size_mb * 1024 * 1024)
    if size > max_size_bytes:
        raise ValidationError(f"File size exceeds the limit of {max_size_mb} MB.")

    # Reset file pointer if supported
    if hasattr(uploaded_file, "seek"):
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

    # 2. Pillow pipeline under localized warning context
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)

        try:
            img = Image.open(uploaded_file)
        except Image.DecompressionBombWarning:
            raise ValidationError("Decompression bomb warning triggered.")
        except Image.DecompressionBombError:
            raise ValidationError("Decompression bomb error triggered.")
        except UnidentifiedImageError:
            raise ValidationError("File is not a valid or supported image.")
        except (OSError, ValueError, Exception) as e:
            raise ValidationError(f"Invalid or corrupt image: {str(e)}")

        # Authoritative Format Check
        img_format = img.format
        if not img_format:
            raise ValidationError("Could not determine image format.")

        img_format = img_format.upper()
        if img_format not in ("JPEG", "PNG", "WEBP"):
            raise ValidationError(f"Unsupported image format: {img_format}")

        # Run verify() to check file integrity
        try:
            img.verify()
        except Exception as e:
            raise ValidationError(f"Corrupt image content: {str(e)}")

        # Reopen file for actual loading and processing since verify() ruins the stream
        if hasattr(uploaded_file, "seek"):
            try:
                uploaded_file.seek(0)
            except Exception:
                pass

        try:
            img = Image.open(uploaded_file)
        except Exception as e:
            raise ValidationError(f"Failed to load image for processing: {str(e)}")

        # Check frame count (reject animations / multi-frame files)
        n_frames = getattr(img, "n_frames", 1)
        is_animated = getattr(img, "is_animated", False)
        if n_frames > 1 or is_animated:
            raise ValidationError("Animated or multi-frame images are not supported.")

        # Orient correct orientation before metadata removal
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        # Calculate and check source pixel safety limit
        width, height = img.size
        max_pixels = getattr(settings, "MEDIA_MAX_SOURCE_IMAGE_PIXELS", 50000000)
        if width * height > max_pixels:
            raise ValidationError("Image dimensions exceed application safety limits.")

        # Resize if width or height exceeds maximum dimensions
        max_w = getattr(settings, "MEDIA_MAX_IMAGE_WIDTH", 4096)
        max_h = getattr(settings, "MEDIA_MAX_IMAGE_HEIGHT", 4096)
        if width > max_w or height > max_h:
            ratio = min(max_w / width, max_h / height)
            new_w = int(width * ratio)
            new_h = int(height * ratio)
            try:
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            except AttributeError:
                img = img.resize((new_w, new_h), Image.LANCZOS)
            width, height = img.size

        # Enforce application-configured MIME whitelist
        allowed_types = getattr(settings, "MEDIA_ALLOWED_IMAGE_TYPES", [])
        if isinstance(allowed_types, str):
            allowed_types = [t.strip().lower() for t in allowed_types.split(",")]

        # Normalize colors, file formats, and mime types
        if img_format == "JPEG":
            target_mime = "image/jpeg"
            target_ext = ".jpg"
            if img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info
            ):
                # Flatten transparent image onto white background
                bg = Image.new("RGB", img.size, (255, 255, 255))
                rgba_img = img.convert("RGBA")
                bg.paste(rgba_img, (0, 0), rgba_img)
                img = bg
            else:
                img = img.convert("RGB")
        elif img_format == "PNG":
            target_mime = "image/png"
            target_ext = ".png"
            if img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info
            ):
                img = img.convert("RGBA")
            else:
                img = img.convert("RGB")
        elif img_format == "WEBP":
            from PIL import features

            if not features.check("webp"):
                raise ValidationError("WebP support is not available in the runtime.")
            target_mime = "image/webp"
            target_ext = ".webp"
            if img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info
            ):
                img = img.convert("RGBA")
            else:
                img = img.convert("RGB")
        else:
            raise ValidationError(f"Unsupported image format: {img_format}")

        if target_mime not in allowed_types:
            raise ValidationError(f"Allowed MIME types exclude: {target_mime}")

        # Encode image to BytesIO (EXIF/GPS metadata is completely stripped here)
        out_buffer = io.BytesIO()
        save_kwargs = {}
        if img_format == "JPEG":
            save_kwargs["quality"] = int(
                getattr(settings, "MEDIA_IMAGE_JPEG_QUALITY", 85)
            )
            save_kwargs["optimize"] = True
        elif img_format == "WEBP":
            save_kwargs["quality"] = int(
                getattr(settings, "MEDIA_IMAGE_WEBP_QUALITY", 85)
            )

        try:
            img.save(out_buffer, format=img_format, **save_kwargs)
        except Exception as e:
            raise ValidationError(f"Failed to encode processed image: {str(e)}")

        final_size = out_buffer.tell()
        if final_size <= 0:
            raise ValidationError("Processed image is empty.")
        if final_size > max_size_bytes:
            raise ValidationError(
                f"Processed image size exceeds the limit of {max_size_mb} MB."
            )

        out_buffer.seek(0)
        file_name = f"processed_{uuid.uuid4()}{target_ext}"
        content_file = ContentFile(out_buffer.read(), name=file_name)

        return ProcessedImage(
            content=content_file,
            extension=target_ext.lstrip("."),
            mime_type=target_mime,
            width=width,
            height=height,
            size=final_size,
        )


def generate_image_storage_name(prefix, owner_id, extension, resource_id=None):
    """
    Generates a UUID-based file path mapping under owners.
    Ignores original user filenames, enforces allowlist, and avoids path traversal.
    """
    if prefix not in ALLOWED_PREFIXES:
        raise ValueError(f"Invalid path prefix: {prefix}")

    owner_str = str(owner_id).strip()
    if not owner_str or not re.match(r"^[a-zA-Z0-9_\-]+$", owner_str):
        raise ValueError("Invalid owner_id format")

    ext_clean = extension.strip().lower().lstrip(".")
    if ext_clean == "jpeg":
        ext_clean = "jpg"
    if ext_clean not in ("jpg", "png", "webp"):
        raise ValueError(f"Unsupported target extension: {extension}")

    unique_id = str(uuid.uuid4())

    if resource_id is not None:
        res_str = str(resource_id).strip()
        if not res_str or not re.match(r"^[a-zA-Z0-9_\-]+$", res_str):
            raise ValueError("Invalid resource_id format")
        return f"{prefix}/{owner_str}/{res_str}/{unique_id}.{ext_clean}"

    return f"{prefix}/{owner_str}/{unique_id}.{ext_clean}"


def safe_delete_storage_object(storage, name, *, context: str) -> bool:
    """
    Safely deletes an object from storage, ignoring empty names and tolerating missing files.
    Logs errors safely without raising exceptions or exposing secrets.
    Returns True if deletion succeeded or file was absent, False if an error occurred.
    """
    if not name:
        return True
    name_str = str(name).strip()
    # Safety checks to prevent directory or prefix deletion
    if not name_str or name_str.endswith("/") or name_str.endswith("\\") or name_str == "." or ".." in name_str:
        import logging
        logging.getLogger(__name__).error(f"[Storage Cleanup] Invalid object name for deletion in context: {context}")
        return False
    try:
        if storage.exists(name_str):
            storage.delete(name_str)
        return True
    except Exception:
        import logging
        logging.getLogger(__name__).error(f"[Storage Cleanup] Failed to delete object in context: {context}")
        return False


def safe_delete_image(storage, name):
    """
    Legacy helper wrapper for backward compatibility.
    """
    return safe_delete_storage_object(storage, name, context="legacy_safe_delete_image")


def build_absolute_media_url(file_field, request=None):
    """
    Centrally normalizes and builds absolute media URLs.
    Rules:
    1. Missing file -> None (null in JSON).
    2. Storage URL starting with http:// or https:// -> return unchanged.
    3. Relative storage URL with request -> request.build_absolute_uri(url).
    4. Relative storage URL without request -> combine with configured public backend origin.
    5. Never expose filesystem paths.
    6. Never duplicate hostnames.
    7. Never return undefined.
    """
    if not file_field:
        return None

    try:
        if isinstance(file_field, str):
            path = file_field
        else:
            name = getattr(file_field, 'name', None)
            if isinstance(name, str) and (name.startswith("http://") or name.startswith("https://")):
                return name
            # Handle FieldFile / ImageFieldFile
            path = file_field.url

        if isinstance(path, str) and (path.startswith("http://") or path.startswith("https://")):
            return path

        if request is not None:
            if isinstance(path, str):
                return request.build_absolute_uri(path)
            return path

        # Fallback to PUBLIC_BACKEND_URL when request is not available
        public_backend_url = getattr(settings, "PUBLIC_BACKEND_URL", "http://localhost:8000")
        base_url = public_backend_url.rstrip("/")

        if isinstance(path, str):
            if not path.startswith("/"):
                path = "/" + path
            return f"{base_url}{path}"

        return path
    except Exception:
        return None


