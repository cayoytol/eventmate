from django.db import models
from django.conf import settings

class Report(models.Model):
    class ContentType(models.TextChoices):
        PROVIDER = 'provider', 'Provider'
        SERVICE = 'service', 'Service'
        REVIEW = 'review', 'Review'
        COMMENT = 'comment', 'Comment'

    class Reason(models.TextChoices):
        SPAM = 'spam', 'Spam'
        FRAUD = 'fraud', 'Fraud'
        ABUSE = 'abuse', 'Abuse'
        INAPPROPRIATE = 'inappropriate', 'Inappropriate'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        IN_REVIEW = 'in_review', 'In Review'
        RESOLVED = 'resolved', 'Resolved'
        REJECTED = 'rejected', 'Rejected'

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_filed'
    )
    content_type = models.CharField(max_length=20, choices=ContentType.choices)
    object_id = models.IntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    message = models.TextField(blank=True, max_length=2000)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports_resolved'
    )
    resolution_note = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Report by {self.reporter.email} on {self.content_type} {self.object_id}"
