from django.core.checks import Error, Warning as CheckWarning, register, Tags
from django.conf import settings


@register(Tags.compatibility)
def check_media_settings(app_configs, **kwargs):
    errors = []

    # 1. Check MEDIA_STORAGE_PROVIDER
    provider = getattr(settings, "MEDIA_STORAGE_PROVIDER", "local")
    if not provider:
        provider = "local"
    provider_norm = str(provider).strip().lower()

    if provider_norm not in ("local", "s3"):
        errors.append(
            Error(
                "Unsupported MEDIA_STORAGE_PROVIDER configuration.",
                hint="Set MEDIA_STORAGE_PROVIDER to 'local' or 's3'.",
                id="media.E001",
            )
        )
        return errors  # Fast-fail for unknown provider

    # 2 & 3. Check S3 requirements
    if provider_norm == "s3":
        bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")
        if not bucket or not str(bucket).strip():
            errors.append(
                Error(
                    "AWS_STORAGE_BUCKET_NAME is not configured.",
                    hint="Set AWS_STORAGE_BUCKET_NAME in environment.",
                    id="media.E002",
                )
            )

        access_key = getattr(settings, "AWS_ACCESS_KEY_ID", "")
        secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", "")
        if (
            not access_key
            or not str(access_key).strip()
            or not secret_key
            or not str(secret_key).strip()
        ):
            errors.append(
                Error(
                    "AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY is not configured.",
                    hint="Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in environment.",
                    id="media.E003",
                )
            )

    # 4. Check image limits validity
    try:
        max_size_mb = float(getattr(settings, "MEDIA_MAX_IMAGE_SIZE_MB", 5))
        if max_size_mb <= 0:
            errors.append(
                Error(
                    "MEDIA_MAX_IMAGE_SIZE_MB must be positive.",
                    id="media.E004",
                )
            )
    except (TypeError, ValueError):
        errors.append(
            Error(
                "MEDIA_MAX_IMAGE_SIZE_MB must be a positive number.",
                id="media.E004",
            )
        )

    try:
        max_pixels = int(getattr(settings, "MEDIA_MAX_SOURCE_IMAGE_PIXELS", 50000000))
        if max_pixels <= 0:
            errors.append(
                Error(
                    "MEDIA_MAX_SOURCE_IMAGE_PIXELS must be positive.",
                    id="media.E004",
                )
            )
    except (TypeError, ValueError):
        errors.append(
            Error(
                "MEDIA_MAX_SOURCE_IMAGE_PIXELS must be a positive integer.",
                id="media.E004",
            )
        )

    try:
        max_w = int(getattr(settings, "MEDIA_MAX_IMAGE_WIDTH", 4096))
        max_h = int(getattr(settings, "MEDIA_MAX_IMAGE_HEIGHT", 4096))
        if max_w <= 0 or max_h <= 0:
            errors.append(
                Error(
                    "MEDIA_MAX_IMAGE_WIDTH and MEDIA_MAX_IMAGE_HEIGHT must be positive.",
                    id="media.E004",
                )
            )
    except (TypeError, ValueError):
        errors.append(
            Error(
                "MEDIA_MAX_IMAGE_WIDTH and MEDIA_MAX_IMAGE_HEIGHT must be positive integers.",
                id="media.E004",
            )
        )

    try:
        jpeg_q = int(getattr(settings, "MEDIA_IMAGE_JPEG_QUALITY", 85))
        webp_q = int(getattr(settings, "MEDIA_IMAGE_WEBP_QUALITY", 85))
        if not (1 <= jpeg_q <= 100) or not (1 <= webp_q <= 100):
            errors.append(
                Error(
                    "MEDIA_IMAGE_JPEG_QUALITY and MEDIA_IMAGE_WEBP_QUALITY must be between 1 and 100.",
                    id="media.E004",
                )
            )
    except (TypeError, ValueError):
        errors.append(
            Error(
                "MEDIA_IMAGE_JPEG_QUALITY and MEDIA_IMAGE_WEBP_QUALITY must be integers between 1 and 100.",
                id="media.E004",
            )
        )

    # 5. Check Pillow WebP support if webp is allowed
    allowed_types = getattr(settings, "MEDIA_ALLOWED_IMAGE_TYPES", [])
    if isinstance(allowed_types, str):
        allowed_types = [t.strip() for t in allowed_types.split(",")]

    if "image/webp" in allowed_types:
        has_webp = False
        try:
            from PIL import features
            has_webp = features.check("webp")
        except Exception:
            try:
                from PIL import WebPImagePlugin  # noqa: F401
                has_webp = True
            except ImportError:
                pass

        if not has_webp:
            errors.append(
                CheckWarning(
                    "WebP image type is allowed but Pillow has no webp support at runtime.",
                    hint="Ensure libwebp is installed and Pillow is compiled with webp support.",
                    id="media.E005",
                )
            )

    return errors
