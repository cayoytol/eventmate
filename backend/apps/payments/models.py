from django.db import models, transaction
from django.utils import timezone
import uuid


class Payment(models.Model):
    """Platform subscription payment"""
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
        
    class CheckoutState(models.TextChoices):
        INITIALIZING = 'initializing', 'Initializing'
        READY = 'ready', 'Ready'
        FAILED = 'failed', 'Failed'
    
    provider_profile = models.ForeignKey(
        'accounts.ProviderProfile',
        on_delete=models.CASCADE,
        related_name='payments'
    )
    subscription = models.ForeignKey(
        'billing.Subscription',
        on_delete=models.PROTECT,
        related_name='payments'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Final amount to pay")
    original_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, help_text="Original plan price")
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, help_text="Applied discount")
    currency = models.CharField(max_length=3, default='KZT')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    checkout_state = models.CharField(
        max_length=20,
        choices=CheckoutState.choices,
        default=CheckoutState.INITIALIZING
    )
    checkout_initialization_started_at = models.DateTimeField(null=True, blank=True)
    checkout_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Immutable plan snapshots
    plan_code_snapshot = models.CharField(max_length=50, blank=True)
    plan_duration_days_snapshot = models.IntegerField(null=True)
    plan_name_ru_snapshot = models.CharField(max_length=100, blank=True)
    plan_name_en_snapshot = models.CharField(max_length=100, blank=True)
    plan_name_kz_snapshot = models.CharField(max_length=100, blank=True)
    
    # Promo snapshots
    promo_code = models.ForeignKey(
        'billing.PromoCode',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payments'
    )
    promo_code_snapshot = models.CharField(max_length=50, blank=True)
    
    # Provider references & idempotency keys
    provider = models.CharField(max_length=50, default='mock')
    provider_payment_id = models.CharField(max_length=100, blank=True)
    provider_reference = models.CharField(max_length=100, blank=True)
    checkout_url = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=100, null=True, blank=True)
    request_fingerprint = models.CharField(max_length=64, null=True, blank=True)
    
    # Provider conversion snapshot
    provider_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    provider_currency = models.CharField(max_length=3, null=True, blank=True)
    conversion_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    conversion_source = models.CharField(max_length=50, null=True, blank=True)
    conversion_locked_at = models.DateTimeField(null=True, blank=True)
    
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider_profile', 'status', 'created_at']),
            models.Index(fields=['provider', 'provider_reference']),
            models.Index(fields=['subscription', 'status']),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gte=0), name='payment_amount_gte_zero'),
            models.CheckConstraint(check=models.Q(original_amount__gte=0), name='payment_original_amount_gte_zero'),
            models.CheckConstraint(check=models.Q(discount_amount__gte=0), name='payment_discount_amount_gte_zero'),
            models.CheckConstraint(check=models.Q(discount_amount__lte=models.F('original_amount')), name='payment_discount_amount_lte_original'),
            models.CheckConstraint(
                check=(
                    models.Q(idempotency_key__isnull=True) |
                    models.Q(idempotency_key="") |
                    (
                        models.Q(request_fingerprint__isnull=False) &
                        ~models.Q(request_fingerprint="")
                    )
                ),
                name="idempotency_key_requires_fingerprint"
            ),
            models.UniqueConstraint(
                fields=["provider_profile", "idempotency_key"],
                condition=(
                    models.Q(idempotency_key__isnull=False)
                    & ~models.Q(idempotency_key="")
                ),
                name="unique_provider_idempotency_key",
            ),
            models.UniqueConstraint(
                fields=["provider", "provider_payment_id"],
                condition=(
                    models.Q(provider_payment_id__isnull=False)
                    & ~models.Q(provider_payment_id="")
                ),
                name="unique_billing_provider_payment_id",
            )
        ]
    
    def __str__(self):
        return f"Payment {self.id} - {self.amount} {self.currency} ({self.status})"
    
    def mark_as_paid(self):
        """Mark payment as paid and activate subscription"""
        if self.status == self.Status.PENDING:
            self.status = self.Status.PAID
            self.paid_at = timezone.now()
            self.save(update_fields=['status', 'paid_at'])
            
            # Activate subscription atomically deactivating older ones
            from apps.billing.services import activate_paid_subscription
            activate_paid_subscription(self.subscription)

            # Trigger: PAYMENT_CONFIRMED (notify provider)
            from apps.notifications.services import create_notification
            from apps.notifications.models import Notification as NotificationModel
            
            create_notification(
                user=self.provider_profile.user,
                n_type=NotificationModel.NotificationType.PAYMENT_CONFIRMED,
                payload={
                    'payment_id': self.id,
                    'subscription_id': self.subscription.id,
                    'amount': self.amount,
                    'currency': self.currency
                }
            )


class PaymentTransaction(models.Model):
    """Transaction model for tracking order payment status and history"""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        'marketplace.Order',
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    provider = models.CharField(max_length=50) # e.g. "mock", "freedompay"
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='KZT')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    provider_payment_id = models.CharField(max_length=100, blank=True)
    provider_reference = models.CharField(max_length=100, blank=True)
    checkout_url = models.URLField(max_length=1000, blank=True)
    idempotency_key = models.CharField(max_length=100, unique=True)
    
    # Provider conversion snapshot
    provider_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    provider_currency = models.CharField(max_length=3, null=True, blank=True)
    conversion_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    conversion_source = models.CharField(max_length=50, null=True, blank=True)
    conversion_locked_at = models.DateTimeField(null=True, blank=True)
    
    raw_response = models.JSONField(default=dict, blank=True)
    
    # Checkout coordination states and attempt tracking
    class CheckoutState(models.TextChoices):
        IDLE = 'idle', 'Idle'
        INITIALIZING = 'initializing', 'Initializing'
        READY = 'ready', 'Ready'
        RETRYABLE_ERROR = 'retryable_error', 'Retryable Error'
        TERMINAL_ERROR = 'terminal_error', 'Terminal Error'
        COMPLETED = 'completed', 'Completed'

    checkout_state = models.CharField(
        max_length=20,
        choices=CheckoutState.choices,
        default=CheckoutState.IDLE
    )
    checkout_initialization_token = models.UUIDField(null=True, blank=True)
    checkout_initialization_started_at = models.DateTimeField(null=True, blank=True)
    
    # Safe error reporting
    checkout_error_code = models.CharField(max_length=50, blank=True)
    checkout_error_at = models.DateTimeField(null=True, blank=True)
    checkout_retry_after = models.PositiveIntegerField(null=True, blank=True)
    
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', 'status']),
            models.Index(fields=['provider', 'provider_reference']),
            models.Index(fields=['created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['order', 'provider'],
                condition=models.Q(status='pending'),
                name='uniq_pending_payment_tx_order_provider'
            )
        ]

    def matches_order_payable_snapshot(self, order) -> bool:
        """Centralized validation to check if transaction matches current order details"""
        return self.amount == order.price_agreed and self.order_id == order.id

    def __str__(self):
        return f"Transaction {self.id} - Order {self.order_id} - {self.amount} {self.currency} ({self.status})"


