from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings

class Category(models.Model):
    name_ru = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100, blank=True)
    name_kz = models.CharField(max_length=100, blank=True)
    slug = models.SlugField(unique=True)
    icon = models.ImageField(upload_to='categories/', null=True, blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name_ru']

    def __str__(self):
        return self.name_ru

class Service(models.Model):
    class PriceType(models.TextChoices):
        FIXED = 'fixed', _('Fixed Price')
        HOURLY = 'hourly', _('Hourly Rate')
        RANGE = 'range', _('Price Range')

    provider = models.ForeignKey('accounts.ProviderProfile', on_delete=models.CASCADE, related_name='services')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='services')
    title = models.CharField(max_length=200)
    description = models.TextField()
    price_type = models.CharField(max_length=20, choices=PriceType.choices, default=PriceType.FIXED)
    price_amount = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.PositiveIntegerField(default=60, help_text=_("Duration in minutes"))
    capacity_per_slot = models.PositiveIntegerField(default=1, help_text=_("Max simultaneous orders"))
    city = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True, default="")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=["latitude", "longitude"], name="service_lat_lng_idx"),
        ]

    def __str__(self):
        return f"{self.title}"

from django.core.exceptions import ValidationError

class ServiceMedia(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='media')
    file = models.ImageField(upload_to='services/')
    is_cover = models.BooleanField(default=False)

    mime_type = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )
    file_size = models.PositiveIntegerField(
        null=True,
        blank=True,
    )
    width = models.PositiveIntegerField(
        null=True,
        blank=True,
    )
    height = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["service"],
                condition=models.Q(is_cover=True),
                name="unique_service_active_cover",
            )
        ]

    def clean(self):
        super().clean()
        if self.is_cover and self.service_id:
            duplicate_exists = (
                ServiceMedia.objects
                .filter(service_id=self.service_id, is_cover=True)
                .exclude(pk=self.pk)
                .exists()
            )
            if duplicate_exists:
                raise ValidationError("Only one active cover image is allowed per service.")


class ServiceFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorite_services')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'service'], name='unique_user_service_favorite')
        ]
        ordering = ['-created_at']

class ProviderFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorite_providers')
    provider_profile = models.ForeignKey('accounts.ProviderProfile', on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'provider_profile'], name='unique_user_provider_favorite')
        ]
        ordering = ['-created_at']
