from django.core.checks import Error, register
from django.conf import settings

@register()
def check_paypal_timeout(app_configs, **kwargs):
    errors = []
    timeout = getattr(settings, 'PAYPAL_CHECKOUT_INITIALIZATION_TIMEOUT_SECONDS', None)
    
    if timeout is not None:
        # Check if integer (and not boolean, since bool inherits from int in Python)
        if not isinstance(timeout, int) or isinstance(timeout, bool):
            errors.append(
                Error(
                    "PAYPAL_CHECKOUT_INITIALIZATION_TIMEOUT_SECONDS must be between 5 and 3600.",
                    id="PAYPAL.E009",
                )
            )
        elif timeout < 5 or timeout > 3600:
            errors.append(
                Error(
                    "PAYPAL_CHECKOUT_INITIALIZATION_TIMEOUT_SECONDS must be between 5 and 3600.",
                    id="PAYPAL.E009",
                )
            )
    return errors
