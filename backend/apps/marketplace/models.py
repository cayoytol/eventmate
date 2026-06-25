from django.db import models, transaction
from django.db.models import Avg, Count
from django.conf import settings

class EventRequest(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'New'
        IN_REVIEW = 'in_review', 'In Review'
        OFFERS = 'offers', 'Accepting Offers'
        CONFIRMED = 'confirmed', 'Confirmed'
        CANCELLED = 'cancelled', 'Cancelled'

    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='requests')
    category = models.ForeignKey('catalog.Category', on_delete=models.PROTECT)
    title = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    event_date = models.DateTimeField()
    event_start_at = models.DateTimeField(null=True, blank=True)
    budget_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    budget_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # New field
    budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Keep for backward compatibility
    description = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    
    # Targeted requests (Stage A1)
    target_provider = models.ForeignKey(
        'accounts.ProviderProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='targeted_requests',
        help_text="If set, only this provider can see the request"
    )
    target_service = models.ForeignKey(
        'catalog.Service',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requests',
        help_text="Service that client contacted about"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

class Offer(models.Model):
    class Status(models.TextChoices):
        SENT = 'sent', 'Sent'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'
        WITHDRAWN = 'withdrawn', 'Withdrawn'

    request = models.ForeignKey(EventRequest, on_delete=models.CASCADE, related_name='offers')
    service = models.ForeignKey('catalog.Service', on_delete=models.CASCADE)
    provider_profile = models.ForeignKey('accounts.ProviderProfile', on_delete=models.CASCADE, related_name='offers')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cover_letter = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SENT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']

class Order(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = 'confirmed', 'Confirmed'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        DISPUTED = 'disputed', 'Disputed'
        CANCELLED = 'cancelled', 'Cancelled'
    
    class PaymentStatus(models.TextChoices):
        UNPAID = 'unpaid', 'Unpaid'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'

    offer = models.OneToOneField(Offer, on_delete=models.PROTECT)
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='client_orders')
    provider_profile = models.ForeignKey('accounts.ProviderProfile', on_delete=models.PROTECT, related_name='provider_orders')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFIRMED)
    payment_status = models.CharField(max_length=16, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)
    
    # Snapshots
    price_agreed = models.DecimalField(max_digits=10, decimal_places=2)
    service_snapshot = models.JSONField(default=dict)
    
    # QR & Execution
    qr_start_token_hash = models.CharField(max_length=128, blank=True)
    qr_finish_token_hash = models.CharField(max_length=128, blank=True)
    checkin_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']


class Review(models.Model):
    """Client review for a completed order"""
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='review')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    provider_profile = models.ForeignKey('accounts.ProviderProfile', on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(help_text="Rating from 1 to 5")
    text = models.TextField(blank=True)
    provider_reply = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Review for order {self.order_id} - {self.rating} stars"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        with transaction.atomic():
            super().save(*args, **kwargs)
            self.update_provider_rating()

    def update_provider_rating(self):
        """Recalculate provider_profile.rating_avg and reviews_count"""
        stats = Review.objects.filter(provider_profile=self.provider_profile).aggregate(
            avg_rating=Avg('rating'),
            total_reviews=Count('id')
        )
        
        self.provider_profile.rating_avg = stats['avg_rating'] or 0.0
        self.provider_profile.reviews_count = stats['total_reviews'] or 0
        self.provider_profile.save(update_fields=['rating_avg', 'reviews_count'])

    def delete(self, *args, **kwargs):
        provider_profile = self.provider_profile
        with transaction.atomic():
            super().delete(*args, **kwargs)
            # Recalculate after deletion
            stats = Review.objects.filter(provider_profile=provider_profile).aggregate(
                avg_rating=Avg('rating'),
                total_reviews=Count('id')
            )
            provider_profile.rating_avg = stats['avg_rating'] or 0.0
            provider_profile.reviews_count = stats['total_reviews'] or 0
            provider_profile.save(update_fields=['rating_avg', 'reviews_count'])

class ReviewMedia(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='media')
    file_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
