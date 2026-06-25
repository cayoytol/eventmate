"""
apps/billing/services/webhooks.py

Central billing webhook processing service.

Responsibilities:
  - Compute payload hash and build deterministic deduplication key
  - Claim a BillingWebhookEvent atomically (create-or-load with select_for_update)
  - Implement crash-recovery: stale 'processing' events are reclaimed after timeout
  - Resolve the linked Payment via safe provider references
  - Validate Decimal amount and normalized currency
  - Dispatch to the appropriate payment state-machine handler
  - Activate subscriptions using immutable Payment snapshots
  - Supersede old effective paid subscriptions atomically
  - Redeem PromoCode exactly once via PromoCodeRedemption guard
  - Emit PAYMENT_CONFIRMED notification after transaction commit

Lock ordering (strictly enforced to prevent deadlocks):
  1. ProviderProfile
  2. Payment
  3. Subscription (the pending one being activated)
  4. Old active/cancelled Subscriptions (rows being superseded)
  5. PromoCode
  6. PromoCodeRedemption (create)

BillingWebhookEvent may be claimed in its own short transaction before business locks.

Security:
  - Never stores raw payload, signature, secrets, card data, tokens
  - Never logs expected/received signatures
  - safe_summary contains only allow-listed fields
  - No network calls are made while locks are held
"""

import hashlib
import json
import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.db import transaction, IntegrityError
from django.db.models import F
from django.utils import timezone
from django.conf import settings

from apps.billing.models import BillingWebhookEvent, Subscription, PromoCode, PromoCodeRedemption
from apps.payments.models import Payment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BILLING_WEBHOOK_PROCESSING_TIMEOUT_SECONDS = getattr(
    settings, 'BILLING_WEBHOOK_PROCESSING_TIMEOUT_SECONDS', 120
)

# Allowed event types
EVENT_PAYMENT_CONFIRMED = 'payment_confirmed'
EVENT_PAYMENT_FAILED = 'payment_failed'
EVENT_PAYMENT_CANCELLED = 'payment_cancelled'
EVENT_PAYMENT_PENDING = 'payment_pending'

TERMINAL_EVENT_TYPES = {EVENT_PAYMENT_CONFIRMED, EVENT_PAYMENT_FAILED, EVENT_PAYMENT_CANCELLED}

# Payment transitions that are valid "success" events
SUCCESS_TRANSITIONS = {EVENT_PAYMENT_CONFIRMED}

# ---------------------------------------------------------------------------
# Payload hashing and dedup key
# ---------------------------------------------------------------------------

def _compute_payload_hash(raw_body: bytes) -> str:
    """SHA-256 hex digest of the raw body bytes."""
    return hashlib.sha256(raw_body).hexdigest()


def _build_deterministic_event_id(provider: str, event_type: str, provider_payment_id: str,
                                   provider_reference: str, payment_status: str,
                                   payload_hash: str) -> str:
    """
    Build a deterministic deduplication key when the provider does not supply
    a unique event_id. Never uses timestamps as identity.
    """
    parts = [
        provider,
        event_type,
        provider_payment_id or '',
        provider_reference or '',
        payment_status or '',
        payload_hash,
    ]
    canonical = '|'.join(parts)
    return 'dedup:' + hashlib.sha256(canonical.encode('utf-8')).hexdigest()


# ---------------------------------------------------------------------------
# Event claim with crash recovery
# ---------------------------------------------------------------------------

def _claim_webhook_event(
    provider: str,
    provider_event_id: str,
    event_type: str,
    provider_payment_id: str,
    provider_reference: str,
    payload_hash: str,
) -> tuple:
    """
    Atomically claim a BillingWebhookEvent row for processing.

    Returns (event, should_process, idempotent_response):
      - should_process=True  → caller should run business logic
      - should_process=False → return idempotent_response immediately

    Handles:
      - Already processed/ignored → idempotent skip
      - Currently processing and fresh → return "processing" response
      - Currently processing and stale → reclaim (one winner via select_for_update)
      - New event → create and claim

    Uses a short atomic transaction isolated from the main business transaction.
    """
    timeout_seconds = getattr(
        settings, 'BILLING_WEBHOOK_PROCESSING_TIMEOUT_SECONDS',
        BILLING_WEBHOOK_PROCESSING_TIMEOUT_SECONDS
    )
    stale_threshold = timezone.now() - timedelta(seconds=timeout_seconds)

    with transaction.atomic():
        # Try create
        try:
            with transaction.atomic():
                event = BillingWebhookEvent.objects.create(
                    provider=provider,
                    provider_event_id=provider_event_id,
                    event_type=event_type,
                    provider_payment_id=provider_payment_id,
                    provider_reference=provider_reference,
                    payload_hash=payload_hash,
                    status=BillingWebhookEvent.Status.PROCESSING,
                    processing_started_at=timezone.now(),
                    attempt_count=1,
                )
                return event, True, None
        except IntegrityError:
            pass  # Already exists; fall through to load

        # Load and lock the existing event
        try:
            event = BillingWebhookEvent.objects.select_for_update().get(
                provider=provider,
                provider_event_id=provider_event_id,
            )
        except BillingWebhookEvent.DoesNotExist:
            # Race: created between our create attempt and this get — try once more
            try:
                with transaction.atomic():
                    event = BillingWebhookEvent.objects.create(
                        provider=provider,
                        provider_event_id=provider_event_id,
                        event_type=event_type,
                        provider_payment_id=provider_payment_id,
                        provider_reference=provider_reference,
                        payload_hash=payload_hash,
                        status=BillingWebhookEvent.Status.PROCESSING,
                        processing_started_at=timezone.now(),
                        attempt_count=1,
                    )
                    return event, True, None
            except IntegrityError:
                # If still fails due to race, query the locked row one final time
                event = BillingWebhookEvent.objects.select_for_update().get(
                    provider=provider,
                    provider_event_id=provider_event_id,
                )

        # Already in a terminal completed state
        if event.status in (
            BillingWebhookEvent.Status.PROCESSED,
            BillingWebhookEvent.Status.IGNORED,
        ):
            return event, False, {
                'status': 'already_processed',
                'event_id': event.id,
            }

        # Still processing
        if event.status == BillingWebhookEvent.Status.PROCESSING:
            if event.processing_started_at and event.processing_started_at > stale_threshold:
                # Fresh — another worker is handling it
                return event, False, {
                    'status': 'processing',
                    'event_id': event.id,
                }
            # Stale — reclaim this event
            logger.info(
                "Reclaiming stale billing webhook event provider=%s event_id=%s attempt=%s",
                provider, provider_event_id, event.attempt_count + 1
            )

        # Claim (new, failed, or stale processing)
        event.status = BillingWebhookEvent.Status.PROCESSING
        event.processing_started_at = timezone.now()
        event.attempt_count = F('attempt_count') + 1
        event.save(update_fields=['status', 'processing_started_at', 'attempt_count'])
        event.refresh_from_db(fields=['attempt_count'])
        return event, True, None


# ---------------------------------------------------------------------------
# Amount validation
# ---------------------------------------------------------------------------

def _validate_amount(amount_str: str, currency_str: str, payment: 'Payment') -> tuple:
    """
    Validate the Decimal amount and currency from the normalized event against Payment.
    If provider_currency and provider_amount snapshots exist, validate against them.
    Returns (ok: bool, error_code: str).
    Never exposes expected payment details in error responses.
    """
    expected_currency = payment.provider_currency if payment.provider_currency else payment.currency
    expected_amount = payment.provider_amount if payment.provider_amount is not None else payment.amount

    # Currency check first
    normalized_currency = (currency_str or '').upper().strip()
    if not normalized_currency:
        return False, 'currency_missing'
    if normalized_currency != expected_currency.upper():
        return False, 'currency_mismatch'

    # Amount check
    if not amount_str and amount_str != 0:
        return False, 'amount_missing'

    try:
        amount = Decimal(str(amount_str))
    except (InvalidOperation, TypeError, ValueError):
        return False, 'amount_invalid'

    import math
    if amount.is_nan() or amount.is_infinite():
        return False, 'amount_invalid'

    if amount < Decimal('0'):
        return False, 'amount_negative'

    amount_quantized = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    if amount_quantized != expected_amount:
        return False, 'amount_mismatch'

    return True, ''


# ---------------------------------------------------------------------------
# Payment resolution
# ---------------------------------------------------------------------------

def _resolve_payment(provider_name: str, normalized: dict) -> 'Payment | None':
    """
    Locate the billing Payment using safe provider references.
    Resolution order:
      1. provider + provider_payment_id
      2. provider + provider_reference

    Verifies:
      - Payment.provider matches provider_name
      - Payment has a linked Subscription
      - Payment.provider_profile matches Subscription.provider_profile
      - The object is apps.payments.Payment (not PaymentTransaction)

    Returns None if resolution fails.
    """
    provider_payment_id = normalized.get('provider_payment_id', '')
    provider_reference = normalized.get('provider_reference', '')

    qs = Payment.objects.select_related('subscription', 'provider_profile')

    payment = None

    if provider_payment_id:
        try:
            payment = qs.get(provider=provider_name, provider_payment_id=provider_payment_id)
        except Payment.DoesNotExist:
            pass
        except Payment.MultipleObjectsReturned:
            logger.error(
                "Multiple billing Payments found for provider=%s provider_payment_id=%s",
                provider_name, provider_payment_id
            )
            return None

    if payment is None and provider_reference:
        try:
            payment = qs.get(provider=provider_name, provider_reference=provider_reference)
        except Payment.DoesNotExist:
            pass
        except Payment.MultipleObjectsReturned:
            logger.error(
                "Multiple billing Payments found for provider=%s provider_reference=%s",
                provider_name, provider_reference
            )
            return None

    if payment is None:
        return None

    # Verify integrity
    if not hasattr(payment, 'subscription') or payment.subscription is None:
        logger.error("Billing Payment %s has no linked Subscription", payment.id)
        return None

    if payment.provider_profile != payment.subscription.provider_profile:
        logger.error(
            "Billing Payment %s provider_profile mismatch with Subscription", payment.id
        )
        return None

    return payment


# ---------------------------------------------------------------------------
# Subscription activation (immutable snapshots)
# ---------------------------------------------------------------------------

def _activate_subscription(subscription: Subscription, payment: Payment, occurred_at_str: str):
    """
    Activate the pending subscription using immutable Payment snapshots.
    start_date uses occurred_at when valid, otherwise timezone.now().
    end_date = start_date + timedelta(days=payment.plan_duration_days_snapshot).

    Validates plan_duration_days_snapshot > 0.
    Repeated success must not reset start_date or extend end_date.
    Called inside an existing atomic transaction with all locks already held.
    """
    if subscription.status == 'active':
        # Already active — idempotent
        return

    duration_days = payment.plan_duration_days_snapshot
    if not duration_days or duration_days <= 0:
        raise ValueError(
            f"Payment {payment.id} has invalid plan_duration_days_snapshot={duration_days}"
        )

    # Determine start_date
    start_date = None
    if occurred_at_str:
        try:
            from django.utils.dateparse import parse_datetime
            parsed = parse_datetime(occurred_at_str)
            if parsed:
                start_date = parsed
        except Exception:
            pass

    if start_date is None:
        start_date = timezone.now()

    end_date = start_date + timedelta(days=duration_days)

    subscription.status = 'active'
    subscription.start_date = start_date
    subscription.end_date = end_date
    subscription.cancelled_at = None  # clear if previously cancelled
    subscription.save(update_fields=['status', 'start_date', 'end_date', 'cancelled_at'])


def _supersede_old_subscriptions(provider_profile, new_subscription: Subscription, activated_at):
    """
    End old overlapping effective paid subscriptions at activation time.
    Must be called inside an atomic transaction with provider_profile already locked.
    Marks overlapping rows 'superseded' and sets end_date to activated_at.
    Does not delete history.
    """
    old_subs = list(
        Subscription.objects.select_for_update().filter(
            provider_profile=provider_profile,
            status__in=['active', 'cancelled'],
        ).exclude(id=new_subscription.id)
    )

    for sub in old_subs:
        if sub.end_date and sub.end_date > activated_at:
            # Overlapping — supersede
            sub.status = 'superseded'
            sub.end_date = activated_at
            sub.save(update_fields=['status', 'end_date'])
        elif sub.end_date is None or sub.end_date <= activated_at:
            # Already expired — just mark expired/superseded
            sub.status = 'superseded'
            sub.save(update_fields=['status'])


# ---------------------------------------------------------------------------
# Promo redemption (exact-once)
# ---------------------------------------------------------------------------

def _redeem_promo_if_applicable(payment: Payment, subscription: Subscription, occurred_at):
    """
    Create a PromoCodeRedemption record and increment PromoCode.used_count exactly once.
    Guards against double-redemption using the OneToOne payment relation.
    Lock order: PromoCode → PromoCodeRedemption (inside existing transaction).

    If payment.promo_code is None: no-op.
    If PromoCodeRedemption already exists for this payment: no-op (idempotent).
    """
    if not payment.promo_code_id:
        return  # No promo to redeem

    # Check existing redemption (OneToOne guard)
    try:
        _ = payment.promo_redemption  # type: ignore[attr-defined]
        # Already redeemed — idempotent
        return
    except PromoCodeRedemption.DoesNotExist:
        pass

    # Lock PromoCode
    promo = PromoCode.objects.select_for_update().get(id=payment.promo_code_id)

    # Create redemption record
    PromoCodeRedemption.objects.create(
        promo_code=promo,
        provider_profile=payment.provider_profile,
        payment=payment,
        subscription=subscription,
        promo_code_snapshot=payment.promo_code_snapshot or promo.code,
        original_amount_snapshot=payment.original_amount or payment.amount,
        discount_amount_snapshot=payment.discount_amount or Decimal('0.00'),
        final_amount_snapshot=payment.amount,
        redeemed_at=occurred_at,
    )

    # Increment used_count atomically
    PromoCode.objects.filter(id=promo.id).update(used_count=F('used_count') + 1)


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

def _handle_payment_confirmed(payment: Payment, normalized: dict):
    """
    Handle a payment_confirmed event.
    Lock order: ProviderProfile → Payment → Subscription → old Subscriptions → PromoCode.
    """
    from apps.accounts.models import ProviderProfile

    with transaction.atomic():
        # 1. Lock ProviderProfile
        ProviderProfile.objects.select_for_update().get(id=payment.provider_profile_id)

        # 2. Lock Payment (re-fetch to get fresh state after lock)
        payment = Payment.objects.select_for_update().get(id=payment.id)

        # 3. Idempotent: already paid
        if payment.status == Payment.Status.PAID:
            return 'skipped'

        # 4. Ignored transitions: paid → anything else handled above
        # Non-pending states that shouldn't be transitioned to paid
        # (paid → failed or cancelled would be caught above since we check == PAID)

        # 5. Lock Subscription
        subscription = Subscription.objects.select_for_update().get(
            id=payment.subscription_id
        )

        # 6. Activate subscription using immutable snapshots
        occurred_at_str = normalized.get('occurred_at', '')
        _activate_subscription(subscription, payment, occurred_at_str)

        # 7. Supersede old paid subscriptions
        _supersede_old_subscriptions(
            payment.provider_profile, subscription, subscription.start_date
        )

        # 8. Mark payment as PAID (atomically)
        payment.status = Payment.Status.PAID
        payment.checkout_state = Payment.CheckoutState.READY
        if not payment.paid_at:
            payment.paid_at = subscription.start_date or timezone.now()
        payment.save(update_fields=['status', 'checkout_state', 'paid_at', 'updated_at'])

        # 9. Exact-once promo redemption
        _redeem_promo_if_applicable(
            payment, subscription,
            occurred_at=subscription.start_date or timezone.now()
        )

    return 'processed'


def _handle_payment_failed(payment: Payment, normalized: dict):
    """
    Handle a payment_failed event.
    Marks payment FAILED and linked pending subscription FAILED.
    Does not touch active subscriptions or redeem promo.
    """
    with transaction.atomic():
        from apps.accounts.models import ProviderProfile
        ProviderProfile.objects.select_for_update().get(id=payment.provider_profile_id)
        payment = Payment.objects.select_for_update().get(id=payment.id)

        # Ignored transitions
        if payment.status in (
            Payment.Status.PAID,
            Payment.Status.FAILED,
            Payment.Status.CANCELLED,
        ):
            return 'skipped'

        subscription = Subscription.objects.select_for_update().get(
            id=payment.subscription_id
        )

        payment.status = Payment.Status.FAILED
        payment.save(update_fields=['status', 'updated_at'])

        if subscription.status == 'pending':
            subscription.status = 'failed'
            subscription.save(update_fields=['status'])

    return 'processed'


def _handle_payment_cancelled(payment: Payment, normalized: dict):
    """
    Handle a payment_cancelled event.
    Marks payment CANCELLED and linked pending subscription CANCELLED (not failed).
    """
    with transaction.atomic():
        from apps.accounts.models import ProviderProfile
        ProviderProfile.objects.select_for_update().get(id=payment.provider_profile_id)
        payment = Payment.objects.select_for_update().get(id=payment.id)

        # Ignored transitions
        if payment.status in (
            Payment.Status.PAID,
            Payment.Status.FAILED,
            Payment.Status.CANCELLED,
        ):
            return 'skipped'

        subscription = Subscription.objects.select_for_update().get(
            id=payment.subscription_id
        )

        payment.status = Payment.Status.CANCELLED
        payment.save(update_fields=['status', 'updated_at'])

        if subscription.status == 'pending':
            subscription.status = 'cancelled'
            subscription.save(update_fields=['status'])

    return 'processed'


def _send_payment_confirmed_notification(payment_id: int):
    """
    Send PAYMENT_CONFIRMED notification to the provider user.
    Must be called via transaction.on_commit() to ensure DB commit is complete.
    Idempotent: duplicate calls are tolerated (notification service handles it).
    Never logs secrets or raw webhook data.
    """
    try:
        from apps.notifications.services import create_notification
        from apps.notifications.models import Notification as NotificationModel
        from apps.payments.models import Payment as PaymentModel

        payment = PaymentModel.objects.select_related('provider_profile__user').get(id=payment_id)
        create_notification(
            user=payment.provider_profile.user,
            n_type=NotificationModel.NotificationType.PAYMENT_CONFIRMED,
            payload={
                'payment_id': payment.id,
                'subscription_id': payment.subscription_id,
                'amount': str(payment.amount),
                'currency': payment.currency,
            }
        )
    except Exception:
        logger.exception(
            "Failed to create PAYMENT_CONFIRMED notification for payment_id=%s", payment_id
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def process_billing_webhook(provider_name: str, adapter, raw_body: bytes) -> dict:
    """
    Main billing webhook processing entry point.

    Called from BillingWebhookView after signature verification.
    Returns a dict with 'status' key:
      - 'processed'         — event successfully processed
      - 'already_processed' — duplicate; idempotent skip
      - 'processing'        — another worker is handling it
      - 'ignored'           — event does not require action
      - 'failed'            — unrecoverable processing error (view returns 500)

    Never raises exceptions to the view layer — always returns a status dict.
    Internal errors are logged without sensitive data.
    """
    # 1. Parse payload
    try:
        parsed_payload = adapter.parse_webhook_payload(raw_body, {})
    except ValueError as exc:
        return {'status': 'failed', 'error_code': 'parse_error', 'detail': str(exc)}

    # 2. Normalize
    try:
        normalized = adapter.normalize_webhook_event(parsed_payload)
    except Exception as exc:
        logger.exception("normalize_webhook_event failed for provider=%s", provider_name)
        return {'status': 'failed', 'error_code': 'normalize_error'}

    # 3. Compute payload hash
    payload_hash = _compute_payload_hash(raw_body)

    # 4. Resolve provider_event_id
    event_id = normalized.get('event_id', '') or ''
    if not event_id:
        event_id = _build_deterministic_event_id(
            provider=provider_name,
            event_type=normalized.get('event_type', ''),
            provider_payment_id=normalized.get('provider_payment_id', ''),
            provider_reference=normalized.get('provider_reference', ''),
            payment_status=normalized.get('payment_status', ''),
            payload_hash=payload_hash,
        )

    event_type = normalized.get('event_type', '')

    # 5. Claim event (short transaction)
    try:
        event, should_process, idempotent_response = _claim_webhook_event(
            provider=provider_name,
            provider_event_id=event_id,
            event_type=event_type,
            provider_payment_id=normalized.get('provider_payment_id', ''),
            provider_reference=normalized.get('provider_reference', ''),
            payload_hash=payload_hash,
        )
    except Exception:
        logger.exception(
            "Failed to claim billing webhook event provider=%s event_id=%s", provider_name, event_id
        )
        return {'status': 'failed', 'error_code': 'claim_error'}

    if not should_process:
        return idempotent_response

    # 6. Handle unknown event types
    if event_type not in TERMINAL_EVENT_TYPES and event_type != EVENT_PAYMENT_PENDING:
        logger.info(
            "Billing webhook: unknown event_type=%s provider=%s; ignoring safely",
            event_type, provider_name
        )
        with transaction.atomic():
            BillingWebhookEvent.objects.filter(id=event.id).update(
                status=BillingWebhookEvent.Status.IGNORED,
                processed_at=timezone.now(),
                error_code='unknown_event_type',
                safe_summary={'event_type': event_type, 'reason': 'unknown_event_type'},
            )
        return {'status': 'ignored', 'event_id': event.id}

    # 7. Pending informational event — record but do not activate
    if event_type == EVENT_PAYMENT_PENDING:
        with transaction.atomic():
            BillingWebhookEvent.objects.filter(id=event.id).update(
                status=BillingWebhookEvent.Status.IGNORED,
                processed_at=timezone.now(),
                safe_summary={'event_type': event_type, 'reason': 'informational_only'},
            )
        return {'status': 'ignored', 'event_id': event.id}

    # 8. Resolve Payment
    payment = _resolve_payment(provider_name, normalized)
    if payment is None:
        with transaction.atomic():
            BillingWebhookEvent.objects.filter(id=event.id).update(
                status=BillingWebhookEvent.Status.FAILED,
                processed_at=timezone.now(),
                error_code='payment_not_found',
                safe_summary={
                    'event_type': event_type,
                    'provider_payment_id': normalized.get('provider_payment_id', ''),
                    'provider_reference': normalized.get('provider_reference', ''),
                    'reason': 'payment_not_found',
                },
            )
        return {'status': 'failed', 'error_code': 'payment_not_found'}

    # 9. Amount & currency validation
    amount_ok, error_code = _validate_amount(
        amount_str=normalized.get('amount', ''),
        currency_str=normalized.get('currency', ''),
        payment=payment,
    )
    if not amount_ok:
        with transaction.atomic():
            BillingWebhookEvent.objects.filter(id=event.id).update(
                payment=payment,
                status=BillingWebhookEvent.Status.FAILED,
                processed_at=timezone.now(),
                error_code=error_code,
                safe_summary={
                    'event_type': event_type,
                    'reason': error_code,
                    'payment_id': payment.id,
                },
            )
        return {'status': 'failed', 'error_code': error_code}

    # 10. Dispatch to event handler
    dispatch_result = 'failed'
    dispatch_error = ''
    payment_id_for_notification = None

    try:
        if event_type == EVENT_PAYMENT_CONFIRMED:
            dispatch_result = _handle_payment_confirmed(payment, normalized)
            if dispatch_result == 'processed':
                payment_id_for_notification = payment.id
        elif event_type == EVENT_PAYMENT_FAILED:
            dispatch_result = _handle_payment_failed(payment, normalized)
        elif event_type == EVENT_PAYMENT_CANCELLED:
            dispatch_result = _handle_payment_cancelled(payment, normalized)
    except Exception:
        logger.exception(
            "Billing webhook business processing failed provider=%s event_id=%s payment=%s",
            provider_name, event_id, payment.id
        )
        dispatch_result = 'failed'
        dispatch_error = 'processing_error'

    # 11. Mark event terminal state
    final_status = (
        BillingWebhookEvent.Status.PROCESSED if dispatch_result in ('processed', 'skipped')
        else BillingWebhookEvent.Status.FAILED
    )
    ignore_reason = 'already_paid' if dispatch_result == 'skipped' else ''

    if dispatch_result == 'skipped':
        final_status = BillingWebhookEvent.Status.IGNORED

    safe_summary = {
        'event_type': event_type,
        'payment_id': payment.id,
        'result': dispatch_result,
    }
    if ignore_reason:
        safe_summary['reason'] = ignore_reason

    with transaction.atomic():
        BillingWebhookEvent.objects.filter(id=event.id).update(
            payment=payment,
            status=final_status,
            processed_at=timezone.now(),
            error_code=dispatch_error,
            safe_summary=safe_summary,
        )

    # 12. Notification after commit (only for fresh confirmed payments)
    if payment_id_for_notification and dispatch_result == 'processed':
        transaction.on_commit(
            lambda pid=payment_id_for_notification: _send_payment_confirmed_notification(pid)
        )

    if dispatch_result == 'failed' and dispatch_error:
        return {'status': 'failed', 'error_code': dispatch_error}

    return {
        'status': 'already_processed' if dispatch_result == 'skipped' else dispatch_result,
        'event_id': event.id,
    }
