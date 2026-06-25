from django.core.checks import Error, register, Tags
from django.db.utils import ProgrammingError, OperationalError


@register(Tags.database)
def check_billing_configuration(app_configs, **kwargs):
    import sys
    if 'test' in sys.argv:
        return []

    errors = []
    
    from apps.billing.models import Plan
    
    try:
        free_plans = Plan.objects.filter(code='free', is_active=True)
        free_count = free_plans.count()
        
        if free_count == 0:
            errors.append(
                Error(
                    "Free plan missing. There must be exactly one active Plan with code='free'.",
                    id="billing.E001",
                )
            )
        elif free_count > 1:
            errors.append(
                Error(
                    "Duplicate Free configuration. More than one active Plan has code='free'.",
                    id="billing.E002",
                )
            )
            
        all_active_plans = Plan.objects.filter(is_active=True)
        for plan in all_active_plans:
            if plan.price < 0:
                errors.append(
                    Error(
                        f"Plan '{plan.name_en}' (id={plan.id}) has a negative price: {plan.price}.",
                        id="billing.E004",
                    )
                )
            if plan.duration_days <= 0:
                errors.append(
                    Error(
                        f"Plan '{plan.name_en}' (id={plan.id}) has an invalid duration: {plan.duration_days} days.",
                        id="billing.E004",
                    )
                )
            if not plan.currency or len(plan.currency) != 3:
                errors.append(
                    Error(
                        f"Plan '{plan.name_en}' (id={plan.id}) has an invalid currency: {plan.currency}.",
                        id="billing.E004",
                    )
                )
                
            limits = plan.limits_json or {}
            for key, val in limits.items():
                if not isinstance(val, bool):
                    try:
                        int_val = int(val)
                        if int_val < -1:
                            errors.append(
                                Error(
                                    f"Plan '{plan.name_en}' limit '{key}' has an invalid value: {int_val} (must be >= -1).",
                                    id="billing.E003",
                                )
                            )
                    except (TypeError, ValueError):
                        errors.append(
                            Error(
                                f"Plan '{plan.name_en}' limit '{key}' has an invalid type: {val}.",
                                id="billing.E003",
                            )
                        )
                        
    except (ProgrammingError, OperationalError):
        # Database tables do not exist yet (e.g. before initial migration)
        # We must return empty errors to avoid startup failure
        pass
        
    return errors


@register(Tags.security)
def check_paypal_configuration(app_configs, **kwargs):
    from django.conf import settings
    from django.core.checks import Error
    import sys
    if 'test' in sys.argv:
        return []

    errors = []
    
    # 1. Billing check
    billing_provider = getattr(settings, 'BILLING_PAYMENT_PROVIDER', 'mock')
    if billing_provider == 'paypal':
        if not getattr(settings, 'PAYPAL_BILLING_CLIENT_ID', ''):
            errors.append(Error("PAYPAL_BILLING_CLIENT_ID is missing.", id="PAYPAL.E001"))
        if not getattr(settings, 'PAYPAL_BILLING_CLIENT_SECRET', ''):
            errors.append(Error("PAYPAL_BILLING_CLIENT_SECRET is missing.", id="PAYPAL.E002"))
        if not getattr(settings, 'PAYPAL_BILLING_WEBHOOK_ID', ''):
            errors.append(Error("PAYPAL_BILLING_WEBHOOK_ID is missing.", id="PAYPAL.E003"))

    # 2. Marketplace check
    payment_provider = getattr(settings, 'PAYMENT_PROVIDER', 'mock')
    if payment_provider == 'paypal':
        if not getattr(settings, 'PAYPAL_ORDERS_CLIENT_ID', ''):
            errors.append(Error("PAYPAL_ORDERS_CLIENT_ID is missing.", id="PAYPAL.E004"))
        if not getattr(settings, 'PAYPAL_ORDERS_CLIENT_SECRET', ''):
            errors.append(Error("PAYPAL_ORDERS_CLIENT_SECRET is missing.", id="PAYPAL.E005"))
        if not getattr(settings, 'PAYPAL_ORDERS_WEBHOOK_ID', ''):
            errors.append(Error("PAYPAL_ORDERS_WEBHOOK_ID is missing.", id="PAYPAL.E006"))

    # 3. Sandbox-only enforcement & conversion checks
    paypal_mode = getattr(settings, 'PAYPAL_MODE', 'sandbox')
    api_url = getattr(settings, 'PAYPAL_API_BASE_URL', '')
    if paypal_mode == 'sandbox' and api_url and 'sandbox' not in api_url:
        errors.append(Error("Non-sandbox PayPal API URL used while PAYPAL_MODE=sandbox.", id="PAYPAL.E007"))

    # Conversion settings checks
    conversion_enabled = getattr(settings, 'PAYPAL_SANDBOX_CONVERSION_ENABLED', True)
    if conversion_enabled:
        if paypal_mode != 'sandbox':
            errors.append(Error("Fixed sandbox currency conversion is only allowed when PAYPAL_MODE=sandbox.", id="PAYPAL.E008"))
        
        rate = getattr(settings, 'PAYPAL_SANDBOX_KZT_PER_USD', None)
        if rate is None or rate <= 0:
            errors.append(Error("PAYPAL_SANDBOX_KZT_PER_USD must be positive.", id="PAYPAL.E009"))
            
        currency = getattr(settings, 'PAYPAL_SANDBOX_CURRENCY', 'USD')
        supported_currencies = {'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'NZD', 'CHF', 'HKD', 'SGD', 'SEK', 'DKK', 'PLN', 'NOK', 'HUF', 'CZK', 'ILS', 'MXN', 'BRL', 'MYR', 'PHP', 'TWD', 'THB'}
        if currency not in supported_currencies:
            errors.append(Error(f"Unsupported target currency {currency} for sandbox conversion.", id="PAYPAL.E010"))

    # 4. Timeout check
    timeout = getattr(settings, 'PAYPAL_CHECKOUT_INITIALIZATION_TIMEOUT_SECONDS', None)
    if timeout is None or timeout <= 0 or timeout > 86400:
        errors.append(Error("PAYPAL_CHECKOUT_INITIALIZATION_TIMEOUT_SECONDS must be positive and less than 86400.", id="PAYPAL.E011"))

    return errors
