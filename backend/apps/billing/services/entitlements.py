from django.utils import timezone
from apps.accounts.models import ProviderProfile
from apps.billing.models import Plan, Subscription


def _get_provider_profile(user_or_provider):
    if isinstance(user_or_provider, ProviderProfile):
        return user_or_provider
    if hasattr(user_or_provider, 'provider_profile'):
        return user_or_provider.provider_profile
    return None


def get_free_plan():
    try:
        return Plan.objects.get(code='free', is_active=True)
    except Plan.DoesNotExist:
        return Plan(
            code='free',
            name_ru='Бесплатный',
            name_en='Free',
            name_kz='Тегін',
            price=0,
            duration_days=3650,
            limits_json={"max_services": 3, "offers_per_month": 10},
            is_active=True
        )


def is_subscription_active(subscription, at=None):
    if not subscription:
        return False
    if at is None:
        at = timezone.now()
    # Lifecycle status permits access if it is active or cancelled
    if subscription.status not in ('active', 'cancelled'):
        return False
    return subscription.start_date <= at and subscription.end_date > at


def get_effective_subscription(provider, at=None):
    if at is None:
        at = timezone.now()
    provider_profile = _get_provider_profile(provider)
    if not provider_profile:
        return None
    
    # Select the latest active/cancelled subscription that covers 'at'
    return Subscription.objects.filter(
        provider_profile=provider_profile,
        status__in=['active', 'cancelled'],
        start_date__lte=at,
        end_date__gt=at
    ).order_by('-created_at').select_related('plan').first()


def get_effective_plan(provider, at=None):
    sub = get_effective_subscription(provider, at=at)
    if sub:
        return sub.plan
    return get_free_plan()


def get_plan_entitlements(provider, at=None):
    plan = get_effective_plan(provider, at=at)
    limits = plan.limits_json or {}
    
    # Entitlement constants (Task 8)
    return {
        "max_active_services": int(limits.get("max_active_services", limits.get("max_services", 3))),
        "max_portfolio_items": int(limits.get("max_portfolio_items", 10)),
        "analytics": bool(limits.get("analytics", False)),
        "ai_features": bool(limits.get("ai_features", False)),
        "featured_placement": bool(limits.get("featured_placement", False)),
        "offers_per_month": int(limits.get("offers_per_month", 10)),
    }


def has_entitlement(provider, entitlement, at=None):
    ents = get_plan_entitlements(provider, at=at)
    return bool(ents.get(entitlement, False))


def get_limit(provider, limit_name, at=None):
    ents = get_plan_entitlements(provider, at=at)
    val = ents.get(limit_name, 0)
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def check_limit(provider, limit_name, current_usage, at=None):
    limit = get_limit(provider, limit_name, at=at)
    if limit < -1:
        return False
    if limit == -1:
        return True
    return current_usage < limit
