import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.db import transaction
from django.core.files.storage import default_storage
from apps.core.media import generate_image_storage_name, safe_delete_storage_object


def portfolio_media_upload_to(instance, filename):
    """
    Computes a secure UUID storage path for uploads.
    """
    ext = filename.split(".")[-1].lower() if "." in filename else "jpg"
    # Fallback if provider_profile is somehow not fully resolved
    provider_id = instance.item.provider_profile.id
    return generate_image_storage_name(
        prefix="portfolio",
        owner_id=provider_id,
        resource_id=instance.item_id,
        extension=ext,
    )


class PortfolioItem(models.Model):
    provider_profile = models.ForeignKey(
        "accounts.ProviderProfile",
        on_delete=models.CASCADE,
        related_name="portfolio_items",
        related_query_name="portfolio_item",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} (Provider: {self.provider_profile_id})"


class PortfolioMedia(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    item = models.ForeignKey(
        PortfolioItem, on_delete=models.CASCADE, related_name="media"
    )

    file = models.ImageField(
        upload_to=portfolio_media_upload_to,
        blank=True,
    )

    file_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
    )

    media_type = models.CharField(
        max_length=10, choices=MediaType.choices, default=MediaType.IMAGE
    )

    # Processed metadata fields
    mime_type = models.CharField(max_length=50, blank=True, default="")
    file_size = models.PositiveIntegerField(null=True, blank=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                check=(
                    (Q(file="") & ~Q(file_url="")) |
                    (~Q(file="") & Q(file_url=""))
                ),
                name="exactly_one_media_source",
            )
        ]

    def clean(self):
        super().clean()
        has_file = bool(self.file)
        has_url = bool(self.file_url)
        if not has_file and not has_url:
            raise ValidationError(
                "Exactly one of 'file' or 'file_url' must be provided."
            )
        if has_file and has_url:
            raise ValidationError("Provide either 'file' or 'file_url', not both.")

    def __str__(self):
        return f"{self.media_type} for Item {self.item_id}"


@receiver(post_delete, sender=PortfolioMedia, dispatch_uid="cleanup_portfolio_media_file_signal")
def cleanup_portfolio_media_file(sender, instance, **kwargs):
    """
    Deletes the exact uploaded storage object after database deletion commits.
    """
    if instance.file and instance.file.name:
        file_name = instance.file.name

        def delete_file():
            safe_delete_storage_object(default_storage, file_name, context="portfolio_media_post_delete")

        transaction.on_commit(delete_file)
