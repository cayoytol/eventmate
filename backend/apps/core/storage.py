import os
from django.core.exceptions import ImproperlyConfigured


def build_media_storages_config(
    provider,
    media_root,
    media_url,
    access_key=None,
    secret_key=None,
    bucket_name=None,
    endpoint_url=None,
    region_name=None,
    custom_domain=None,
    querystring_auth=True,
    addressing_style=None,
    signature_version=None,
):
    """
    Constructs the Django STORAGES dictionary dynamically.
    Fails fast for invalid providers or missing S3 credentials/bucket.
    """
    if not provider:
        provider = "local"

    provider_norm = provider.strip().lower()

    if provider_norm not in ("local", "s3"):
        raise ImproperlyConfigured(
            "Unsupported MEDIA_STORAGE_PROVIDER configuration."
        )

    staticfiles_config = {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    }

    if provider_norm == "local":
        return {
            "default": {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
                "OPTIONS": {
                    "location": media_root,
                    "base_url": media_url,
                },
            },
            "staticfiles": staticfiles_config,
        }

    # S3 Mode: Validate required credentials
    # Credentials/bucket name must be configured.
    # Note: secrets must never be printed/logged.
    if not access_key or not secret_key or not bucket_name:
        raise ImproperlyConfigured(
            "Unsupported MEDIA_STORAGE_PROVIDER configuration."
        )

    options = {
        "access_key": access_key,
        "secret_key": secret_key,
        "bucket_name": bucket_name,
        "default_acl": None,
        "file_overwrite": False,
        "querystring_auth": bool(querystring_auth),
    }

    # Optional options passed only when non-empty
    if endpoint_url and endpoint_url.strip():
        options["endpoint_url"] = endpoint_url.strip()
    if region_name and region_name.strip():
        options["region_name"] = region_name.strip()
    if custom_domain and custom_domain.strip():
        options["custom_domain"] = custom_domain.strip()
    if addressing_style and addressing_style.strip():
        options["addressing_style"] = addressing_style.strip()
    if signature_version and signature_version.strip():
        options["signature_version"] = signature_version.strip()

    return {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": options,
        },
        "staticfiles": staticfiles_config,
    }
