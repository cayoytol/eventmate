import hashlib
import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.conf import settings

from apps.accounts.models import ProviderProfile
from apps.billing.models import Plan, Subscription, PromoCode
from apps.payments.models import Payment
from apps.billing.exceptions import IdempotencyConflictError, PaymentAdapterError
from .payment_adapters import get_subscription_payment_adapter

logger = logging.getLogger(__name__)

def calculate_subscription_price(plan, promo_code=None, at=None):
    """Calculate the discount and final price for a subscription plan using Decimal math"""
    if at is None:
        at = timezone.now()
        
    original_amount = Decimal(str(plan.price))
    discount_amount = Decimal("0.00")
    
    if promo_code:
        # Check active and validity (except used_count preview)
        is_promo_active = promo_code.is_active
        is_expired = promo_code.expires_at and promo_code.expires_at < at
        is_started = not promo_code.starts_at or promo_code.starts_at <= at
        
        # Check plan eligibility
        eligible = True
        if promo_code.eligible_plans.exists():
            eligible = promo_code.eligible_plans.filter(id=plan.id).exists()
            
        if is_promo_active and is_started and not is_expired and eligible:
            discount_val = Decimal(str(promo_code.discount_amount))
            if promo_code.discount_type == 'percentage':
                discount_amount = original_amount * discount_val / Decimal("100")
            elif promo_code.discount_type == 'fixed':
                discount_amount = discount_val
                
            # Bounds
            discount_amount = min(discount_amount, original_amount)
            discount_amount = max(Decimal("0.00"), discount_amount)
            
    # Quantize everything ROUND_HALF_UP
    original_amount = original_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    discount_amount = discount_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    final_amount = (original_amount - discount_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    return {
        "original_amount": original_amount,
        "discount_amount": discount_amount,
        "final_amount": final_amount,
        "currency": plan.currency or "KZT"
    }


def generate_request_fingerprint(provider_profile_id, plan_code, promo_code_str):
    """Generate SHA-256 fingerprint representing stable user intent"""
    data = {
        "provider_profile_id": provider_profile_id,
        "operation": "subscription_checkout",
        "plan_code": plan_code,
        "promo_code": promo_code_str.strip().upper() if promo_code_str else None
    }
    dumped = json.dumps(data, sort_keys=True)
    return hashlib.sha256(dumped.encode('utf-8')).hexdigest()


def create_subscription_checkout(provider_profile, plan=None, promo_code_str=None, idempotency_key=None, locale=None, plan_code=None):
    """Create or reuse subscription checkout with idempotency and two-phase adapter invocation.
    
    Pass either ``plan`` (a Plan instance) or ``plan_code`` (a string).  If ``plan_code`` is
    given and ``plan`` is None the function fetches the Plan from the database.
    """
    if plan is None:
        if plan_code is None:
            raise ValueError("Either 'plan' or 'plan_code' must be provided")
        plan = Plan.objects.get(code=plan_code)

    # 1. Normalize idempotency_key
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if idempotency_key == "":
            idempotency_key = None
            
    # 2. Get promo code
    promo_code = None
    if promo_code_str:
        promo_code_str = promo_code_str.strip().upper()
        try:
            promo_code = PromoCode.objects.get(code=promo_code_str)
        except PromoCode.DoesNotExist:
            pass # calculated as invalid in pricing
            
    # 3. Calculate dynamic prices
    prices = calculate_subscription_price(plan, promo_code)
    
    # 4. Generate stable fingerprint
    fingerprint = generate_request_fingerprint(provider_profile.id, plan.code, promo_code_str)
    
    # Configuration timeout
    init_timeout = getattr(settings, 'BILLING_CHECKOUT_INITIALIZATION_TIMEOUT_SECONDS', 60)
    
    payment = None
    subscription = None
    is_reused = False
    owned_initialization = False
    
    # ==========================================
    # Phase A: Short DB Transaction to lock and setup
    # ==========================================
    with transaction.atomic():
        # Lock provider row
        provider_profile = ProviderProfile.objects.select_for_update().get(id=provider_profile.id)
        
        # Validate plan limits & parameters
        if not plan.is_active:
            raise PaymentAdapterError("Cannot checkout an inactive plan")
        if plan.code == 'free':
            raise PaymentAdapterError("Free plan cannot be checked out via billing transactions")
            
        # Check idempotency first if key exists
        if idempotency_key:
            existing_payment = Payment.objects.filter(
                provider_profile=provider_profile,
                idempotency_key=idempotency_key
            ).select_related('subscription').first()
            
            if existing_payment:
                # Compare fingerprints
                if existing_payment.request_fingerprint != fingerprint:
                    raise IdempotencyConflictError()
                    
                # If paid, never recreate or double call
                if existing_payment.status == Payment.Status.PAID:
                    raise PaymentAdapterError("This transaction is already paid")
                    
                # Check states
                if existing_payment.checkout_state == Payment.CheckoutState.READY:
                    return existing_payment, existing_payment.subscription, True
                    
                elif existing_payment.checkout_state == Payment.CheckoutState.INITIALIZING:
                    age = (timezone.now() - existing_payment.checkout_initialization_started_at).total_seconds()
                    if age < init_timeout:
                        # Return HTTP 202 (Handled in views)
                        return existing_payment, existing_payment.subscription, False
                    else:
                        # Stale initialization timeout - reclaim it!
                        existing_payment.checkout_initialization_started_at = timezone.now()
                        existing_payment.save(update_fields=['checkout_initialization_started_at'])
                        payment = existing_payment
                        subscription = existing_payment.subscription
                        owned_initialization = True
                        is_reused = False
                        
                elif existing_payment.checkout_state == Payment.CheckoutState.FAILED:
                    # Re-initialize the failed payment row to maintain idempotency constraints
                    existing_payment.status = Payment.Status.PENDING
                    existing_payment.checkout_state = Payment.CheckoutState.INITIALIZING
                    existing_payment.checkout_initialization_started_at = timezone.now()
                    existing_payment.save(update_fields=['status', 'checkout_state', 'checkout_initialization_started_at'])
                    payment = existing_payment
                    subscription = existing_payment.subscription
                    owned_initialization = True
                    is_reused = False
                    
        # No key, or no matching key found - attempt reuse of compatible pending checkouts
        if not payment and not idempotency_key:
            from django.db.models import Q
            reusable = Payment.objects.filter(
                provider_profile=provider_profile,
                status=Payment.Status.PENDING,
                plan_code_snapshot=plan.code,
                promo_code=promo_code,
                amount=prices['final_amount'],
                provider=getattr(settings, 'BILLING_PAYMENT_PROVIDER', 'mock'),
            ).filter(
                # Case 1: READY state - checkout_url must be present, checkout_expires_at in the future
                Q(
                    checkout_state=Payment.CheckoutState.READY,
                    checkout_expires_at__gt=timezone.now()
                ) & ~Q(checkout_url="")
                |
                # Case 2: INITIALIZING state - freshness determined by initialization started timestamp
                Q(
                    checkout_state=Payment.CheckoutState.INITIALIZING
                )
            ).select_related('subscription').first()

            
            if reusable:
                if reusable.checkout_state == Payment.CheckoutState.READY:
                    return reusable, reusable.subscription, True
                elif reusable.checkout_state == Payment.CheckoutState.INITIALIZING:
                    age = (timezone.now() - reusable.checkout_initialization_started_at).total_seconds()
                    if age < init_timeout:
                        return reusable, reusable.subscription, False
                    else:
                        # Reclaim stale compat checkout
                        reusable.checkout_initialization_started_at = timezone.now()
                        reusable.save(update_fields=['checkout_initialization_started_at'])
                        payment = reusable
                        subscription = reusable.subscription
                        owned_initialization = True
                        is_reused = False
                        
        # If still not found, create new pending database record
        if not payment:
            # Create subscription
            subscription = Subscription.objects.create(
                provider_profile=provider_profile,
                plan=plan,
                start_date=None,
                end_date=None,
                status='pending'
            )
            
            # Create payment
            payment = Payment.objects.create(
                provider_profile=provider_profile,
                subscription=subscription,
                amount=prices['final_amount'],
                original_amount=prices['original_amount'],
                discount_amount=prices['discount_amount'],
                currency=prices['currency'],
                status=Payment.Status.PENDING,
                checkout_state=Payment.CheckoutState.INITIALIZING,
                checkout_initialization_started_at=timezone.now(),
                plan_code_snapshot=plan.code,
                plan_duration_days_snapshot=plan.duration_days,
                plan_name_ru_snapshot=plan.name_ru or "Plan",
                plan_name_en_snapshot=plan.name_en or "Plan",
                plan_name_kz_snapshot=plan.name_kz or "Plan",
                promo_code=promo_code,
                promo_code_snapshot=promo_code.code if promo_code else "",
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint if idempotency_key else None
            )
            owned_initialization = True
            is_reused = False
            
    # ==========================================
    # Phase B: Outside Database Transaction (Network adapter calls)
    # ==========================================
    if owned_initialization:
        try:
            adapter = get_subscription_payment_adapter()
            checkout_data = adapter.create_checkout(payment, locale=locale)
        except Exception as e:
            logger.error(f"Checkout generation failed in payment adapter: {e}")
            # Mark database state as failed
            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(id=payment.id)
                payment.status = Payment.Status.FAILED
                payment.checkout_state = Payment.CheckoutState.FAILED
                payment.raw_response = {"error": str(e)}
                payment.save(update_fields=['status', 'checkout_state', 'raw_response'])
                
                # Update subscription to failed only if no other active/pending subscriptions
                sub = payment.subscription
                sub.status = 'failed'
                sub.save(update_fields=['status'])
            raise PaymentAdapterError(f"Checkout failed: {str(e)}")
            
        # ==========================================
        # Phase C: Short DB Transaction to commit adapter data
        # ==========================================
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(id=payment.id)
            payment.provider_payment_id = checkout_data['provider_payment_id']
            payment.provider_reference = checkout_data['provider_reference']
            payment.checkout_url = checkout_data['checkout_url']
            payment.checkout_expires_at = checkout_data['checkout_expires_at']
            payment.raw_response = checkout_data['raw_response']
            payment.checkout_state = Payment.CheckoutState.READY
            payment.save(update_fields=[
                'provider_payment_id', 'provider_reference', 'checkout_url',
                'checkout_expires_at', 'raw_response', 'checkout_state'
            ])
            
    return payment, subscription, is_reused
