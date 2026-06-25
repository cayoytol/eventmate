from django.db import models
from django.conf import settings

class AuditLog(models.Model):
    class Action(models.TextChoices):
        REPORT_STATUS_CHANGED = 'REPORT_STATUS_CHANGED', 'Report Status Changed'
        PROVIDER_BLOCKED = 'PROVIDER_BLOCKED', 'Provider Blocked'
        PROVIDER_UNBLOCKED = 'PROVIDER_UNBLOCKED', 'Provider Unblocked'

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=50, choices=Action.choices)
    target_type = models.CharField(max_length=50)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        actor_email = self.actor.email if self.actor else 'System'
        return f"{self.action} on {self.target_type} {self.target_id} by {actor_email}"
