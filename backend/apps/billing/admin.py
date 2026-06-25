from django.contrib import admin
from .models import Plan, Subscription, PromoCode, PromoCodeRedemption, BillingWebhookEvent


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name_en', 'price', 'duration_days', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name_en', 'name_ru', 'name_kz')
    ordering = ('price',)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'provider_profile', 'plan', 'status', 'start_date', 'end_date', 'created_at')
    list_filter = ('status', 'plan')
    search_fields = ('provider_profile__user__email',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_percent', 'max_uses', 'used_count', 'is_active', 'expires_at', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('code',)
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)


@admin.register(PromoCodeRedemption)
class PromoCodeRedemptionAdmin(admin.ModelAdmin):
    """
    Immutable redemption history. Financial snapshots are read-only.
    Do not allow deletion of historical redemption records.
    """
    list_display = (
        'id', 'promo_code_snapshot', 'provider_profile', 'payment',
        'final_amount_snapshot', 'redeemed_at', 'created_at'
    )
    list_filter = ('promo_code',)
    search_fields = ('promo_code_snapshot', 'provider_profile__user__email', 'payment__id')
    ordering = ('-created_at',)
    readonly_fields = (
        'promo_code', 'provider_profile', 'payment', 'subscription',
        'promo_code_snapshot',
        'original_amount_snapshot', 'discount_amount_snapshot', 'final_amount_snapshot',
        'redeemed_at', 'created_at',
    )

    def has_delete_permission(self, request, obj=None):
        # Never allow deleting historical redemption records
        return False

    def has_add_permission(self, request):
        # Created only by the webhook service; not manually
        return False


@admin.register(BillingWebhookEvent)
class BillingWebhookEventAdmin(admin.ModelAdmin):
    """
    Billing webhook event audit log.
    Never displays full payload, signatures, secrets, or card data.
    safe_summary contains only allow-listed fields.
    """
    list_display = (
        'id', 'provider', 'short_event_id', 'event_type', 'status',
        'payment', 'attempt_count', 'received_at', 'processed_at'
    )
    list_filter = ('provider', 'status', 'event_type')
    search_fields = ('provider', 'event_type', 'payment__id')
    ordering = ('-received_at',)
    readonly_fields = (
        'provider', 'provider_event_id', 'event_type', 'payment',
        'provider_payment_id', 'provider_reference', 'payload_hash',
        'status', 'safe_summary', 'error_code',
        'processing_started_at', 'attempt_count',
        'received_at', 'processed_at', 'created_at', 'updated_at',
    )

    def short_event_id(self, obj):
        """Display only first 24 chars of event ID for readability."""
        eid = obj.provider_event_id or ''
        return eid[:24] + ('…' if len(eid) > 24 else '')
    short_event_id.short_description = 'Event ID (short)'

    def has_delete_permission(self, request, obj=None):
        # Webhook events are audit records — no deletion
        return False

    def has_add_permission(self, request):
        # Created only by the webhook service
        return False
