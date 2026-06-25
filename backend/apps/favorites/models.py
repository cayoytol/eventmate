from django.db import models
from django.conf import settings

class Favorite(models.Model):
    class ContentType(models.TextChoices):
        SERVICE = 'service', 'Service'
        PROVIDER = 'provider', 'Provider'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='favorites'
    )
    content_type = models.CharField(max_length=10, choices=ContentType.choices)
    object_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'content_type', 'object_id'],
                name='unique_user_favorite'
            )
        ]
        indexes = [
            models.Index(fields=['user', 'content_type', 'object_id']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.content_type} {self.object_id}"
