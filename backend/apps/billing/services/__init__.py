from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from apps.accounts.models import ProviderProfile
from apps.billing.models import Plan, Subscription
from .entitlements import (
    get_free_plan,
    get_effective_subscription,
    get_effective_plan,
    get_plan_entitlements,
    has_entitlement,
    get_limit,
    check_limit,
    is_subscription_active,
)
from .checkout import create_subscription_checkout, calculate_subscription_price
from .webhooks import process_billing_webhook


def get_active_subscription(provider_profile):
    return get_effective_subscription(provider_profile)


def get_provider_plan(provider_profile):
    return get_effective_plan(provider_profile)


def get_provider_limits(provider_profile):
    return get_plan_entitlements(provider_profile)


@transaction.atomic
def create_subscription(provider_profile, plan):
    """Create new subscription, deactivating previous ones
    
    For paid plans (price > 0), subscription is created as inactive (pending) with null dates.
    It will be activated after payment confirmation.
    Free plan is activated immediately.
    """
    provider_profile = ProviderProfile.objects.select_for_update().get(id=provider_profile.id)
    
    # Load and lock active subscriptions
    active_subs = list(Subscription.objects.select_for_update().filter(
        provider_profile=provider_profile,
        status__in=['active', 'cancelled']
    ))
    
    now = timezone.now()
    is_free = (plan.price == 0)
    status = 'active' if is_free else 'pending'
    
    if is_free:
        for sub in active_subs:
            sub.status = 'expired'
            sub.save(update_fields=['status'])
            
    # For free plan, set active dates immediately. For paid plans (pending), dates are null.
    start_date = now if is_free else None
    end_date = now + timedelta(days=plan.duration_days) if is_free else None
    
    subscription = Subscription.objects.create(
        provider_profile=provider_profile,
        plan=plan,
        start_date=start_date,
        end_date=end_date,
        status=status
    )
    
    return subscription


@transaction.atomic
def activate_paid_subscription(subscription):
    """Mark a paid subscription as active, closing older ones atomically"""
    provider_profile = subscription.provider_profile
    ProviderProfile.objects.select_for_update().get(id=provider_profile.id)
    
    active_subs = list(Subscription.objects.select_for_update().filter(
        provider_profile=provider_profile,
        status__in=['active', 'cancelled']
    ).exclude(id=subscription.id))
    
    now = timezone.now()
    for sub in active_subs:
        sub.status = 'expired'
        sub.save(update_fields=['status'])
        
    subscription.status = 'active'
    subscription.start_date = now
    subscription.end_date = now + timedelta(days=subscription.plan.duration_days)
    subscription.save(update_fields=['status', 'start_date', 'end_date'])
    return subscription


@transaction.atomic
def check_service_limit(provider_profile):
    """Check if provider can create more services (concurrency-safe)"""
    from apps.catalog.models import Service
    
    provider_profile = ProviderProfile.objects.select_for_update().get(id=provider_profile.id)
    current_count = Service.objects.filter(
        provider=provider_profile,
        is_active=True
    ).count()
    
    return check_limit(provider_profile, 'max_active_services', current_count)


@transaction.atomic
def check_offer_limit(provider_profile):
    """Check if provider can create more offers this month (concurrency-safe)"""
    from apps.marketplace.models import Offer
    
    provider_profile = ProviderProfile.objects.select_for_update().get(id=provider_profile.id)
    
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    current_count = Offer.objects.filter(
        provider_profile=provider_profile,
        created_at__gte=month_start
    ).count()
    
    return check_limit(provider_profile, 'offers_per_month', current_count)


@transaction.atomic
def check_portfolio_limit(provider_profile):
    """Check if provider can create more portfolio items (concurrency-safe)"""
    from apps.portfolio.models import PortfolioItem
    
    provider_profile = ProviderProfile.objects.select_for_update().get(id=provider_profile.id)
    current_count = PortfolioItem.objects.filter(
        provider_profile=provider_profile
    ).count()
    
    return check_limit(provider_profile, 'max_portfolio_items', current_count)
