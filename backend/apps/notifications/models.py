from django.db import models
from django.conf import settings

class Notification(models.Model):
    class NotificationType(models.TextChoices):
        NEW_REQUEST = 'new_request', 'New Request'
        NEW_OFFER = 'new_offer', 'New Offer'
        OFFER_ACCEPTED = 'offer_accepted', 'Offer Accepted'
        OFFER_REJECTED = 'offer_rejected', 'Offer Rejected'
        ORDER_CREATED = 'order_created', 'Order Created'
        ORDER_PAID = 'order_paid', 'Order Paid'
        ORDER_COMPLETED = 'order_completed', 'Order Completed'
        NEW_REVIEW = 'new_review', 'New Review'
        PROVIDER_REPLY = 'provider_reply', 'Provider Reply'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200, default='')
    message = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=NotificationType.choices)
    payload = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} for {self.user.email} - Read: {self.is_read}"
