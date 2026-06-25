from django.db import models
from django.utils import timezone


class Plan(models.Model):
    """Subscription plan"""
    code = models.CharField(max_length=50, unique=True)
    name_ru = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    name_kz = models.CharField(max_length=100)
    price = models.IntegerField(help_text="Price in tenge")
    currency = models.CharField(max_length=3, default='KZT')
    duration_days = models.IntegerField(help_text="Plan duration in days")
    limits_json = models.JSONField(
        default=dict,
        help_text='Format: {"max_services": int, "offers_per_month": int}'
    )
    is_active = models.BooleanField(default=True)
    is_recommended = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    description_ru = models.TextField(blank=True, default='')
    description_en = models.TextField(blank=True, default='')
    description_kz = models.TextField(blank=True, default='')
    
    class Meta:
        ordering = ['sort_order', 'price']
    
    def __str__(self):
        return f"{self.name_en} ({self.code}) (₸{self.price})"


class Subscription(models.Model):
    """Provider subscription to a plan"""
    provider_profile = models.ForeignKey(
        'accounts.ProviderProfile',
        on_delete=models.CASCADE,
        related_name='subscriptions'
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('expired', 'Expired'),
            ('cancelled', 'Cancelled'),
            ('pending', 'Pending'),
            ('failed', 'Failed'),
            ('superseded', 'Superseded'),
        ],
        default='active'
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider_profile', 'status', 'created_at']),
            models.Index(fields=['status']),
        ]
    
    @property
    def is_active(self):
        """Legacy property wrapper for dynamic active status"""
        from apps.billing.services.entitlements import is_subscription_active
        return is_subscription_active(self)
    
    def __str__(self):
        return f"{self.provider_profile} - {self.plan} (status: {self.status})"
    
    @property
    def is_currently_active(self):
        """Deprecated: use entitlements service instead.
        Kept for backward compatibility.
        """
        from apps.billing.services.entitlements import is_subscription_active
        return is_subscription_active(self)


class PromoCode(models.Model):
    """Promo code for plans"""
    code = models.CharField(max_length=50, unique=True)
    discount_percent = models.PositiveIntegerField(null=True, blank=True)  # Deprecated
    discount_type = models.CharField(
        max_length=20,
        choices=[
            ('percentage', 'Percentage'),
            ('fixed', 'Fixed Amount')
        ],
        default='percentage'
    )
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_uses = models.PositiveIntegerField()
    used_count = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    eligible_plans = models.ManyToManyField(Plan, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.discount_amount is not None:
            if self.discount_type == 'percentage':
                if self.discount_amount <= 0 or self.discount_amount > 100:
                    raise ValidationError("Percentage discount must be between 0 and 100.")
            elif self.discount_type == 'fixed':
                if self.discount_amount <= 0:
                    raise ValidationError("Fixed discount amount must be greater than 0.")

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} ({self.discount_type}: {self.discount_amount})"

    @property
    def is_valid(self):
        """Deprecated: use promo validation service/serializer instead"""
        from django.utils import timezone
        if not self.is_active:
            return False
        if self.used_count >= self.max_uses:
            return False
        now = timezone.now()
        if self.starts_at and self.starts_at > now:
            return False
        if self.expires_at and self.expires_at < now:
            return False
        return True


class PromoCodeRedemption(models.Model):
    """
    Exact-once redemption record for a promo code applied to a billing payment.
    Created atomically with subscription activation; used as a guard against
    double-redemption on duplicate webhook events.
    Financial snapshots are immutable after creation.
    """
    promo_code = models.ForeignKey(
        PromoCode,
        on_delete=models.PROTECT,
        related_name='redemptions',
        help_text="The promo code that was redeemed"
    )
    provider_profile = models.ForeignKey(
        'accounts.ProviderProfile',
        on_delete=models.PROTECT,
        related_name='promo_redemptions',
        help_text="Provider who redeemed the promo code"
    )
    payment = models.OneToOneField(
        'payments.Payment',
        on_delete=models.PROTECT,
        related_name='promo_redemption',
        help_text="The billing payment this redemption is tied to (one redemption per payment)"
    )
    subscription = models.ForeignKey(
        'billing.Subscription',
        on_delete=models.PROTECT,
        related_name='promo_redemptions',
        help_text="The subscription activated by this redemption"
    )
    promo_code_snapshot = models.CharField(
        max_length=50,
        help_text="Immutable code string at redemption time"
    )
    original_amount_snapshot = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Original plan price at checkout time (Decimal)"
    )
    discount_amount_snapshot = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Applied discount amount at checkout time (Decimal)"
    )
    final_amount_snapshot = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Final paid amount at checkout time (Decimal)"
    )
    redeemed_at = models.DateTimeField(
        help_text="When the redemption was committed (webhook confirmed timestamp)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['promo_code', 'provider_profile']),
            models.Index(fields=['payment']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(original_amount_snapshot__gte=0),
                name='promo_redemption_original_gte_zero'
            ),
            models.CheckConstraint(
                check=models.Q(discount_amount_snapshot__gte=0),
                name='promo_redemption_discount_gte_zero'
            ),
            models.CheckConstraint(
                check=models.Q(final_amount_snapshot__gte=0),
                name='promo_redemption_final_gte_zero'
            ),
            models.CheckConstraint(
                check=models.Q(discount_amount_snapshot__lte=models.F('original_amount_snapshot')),
                name='promo_redemption_discount_lte_original'
            ),
        ]

    def __str__(self):
        return f"Redemption: {self.promo_code_snapshot} for payment {self.payment_id}"


class BillingWebhookEvent(models.Model):
    """
    Audit record for incoming billing provider webhook events.
    Stores only allow-listed safe_summary — never raw body, signatures,
    secret keys, card data, tokens, or complete provider metadata.
    Unique constraint on (provider, provider_event_id) provides idempotency.
    When provider_event_id is absent, a deterministic deduplication key is
    computed from provider + event_type + provider references + payload hash
    and stored as provider_event_id.
    """

    class Status(models.TextChoices):
        RECEIVED = 'received', 'Received'
        PROCESSING = 'processing', 'Processing'
        PROCESSED = 'processed', 'Processed'
        IGNORED = 'ignored', 'Ignored'
        FAILED = 'failed', 'Failed'

    provider = models.CharField(max_length=50, help_text="Billing provider name (e.g. 'mock')")
    provider_event_id = models.CharField(
        max_length=200,
        help_text="Unique event ID from provider, or deterministic dedup key when absent"
    )
    event_type = models.CharField(
        max_length=50,
        help_text="Normalized event type: payment_confirmed, payment_failed, payment_cancelled, etc."
    )
    payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='webhook_events',
        help_text="Resolved billing Payment (nullable until resolution succeeds)"
    )
    provider_payment_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Provider's payment ID from the event payload"
    )
    provider_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Provider's reference string from the event payload"
    )
    payload_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hex digest of the raw request body for deduplication and audit"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RECEIVED,
        db_index=True
    )
    safe_summary = models.JSONField(
        default=dict,
        blank=True,
        help_text="Allow-listed safe fields only. Never store secrets, signatures, or card data."
    )
    error_code = models.CharField(
        max_length=100,
        blank=True,
        help_text="Short machine-readable error code; no sensitive exception text"
    )
    processing_started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When processing began; used for stale reclaim detection"
    )
    attempt_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of processing attempts (incremented atomically)"
    )
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['provider', 'status']),
            models.Index(fields=['payment']),
            models.Index(fields=['status', 'processing_started_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['provider', 'provider_event_id'],
                name='unique_billing_webhook_event'
            ),
        ]

    def __str__(self):
        return f"BillingWebhookEvent[{self.provider}:{self.provider_event_id}] status={self.status}"
