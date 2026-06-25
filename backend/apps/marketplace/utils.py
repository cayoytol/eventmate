from apps.marketplace.models import Order

def get_order_qr_capabilities(order, user) -> dict:
    """
    Centralized helper to compute QR capability flags for a user-order pair.
    Safely handles anonymous users, missing profiles, and staff overrides.
    """
    capabilities = {
        "is_client_owner": False,
        "is_assigned_provider": False,
        "can_generate_start": False,
        "can_generate_finish": False,
        "can_check_in": False,
        "can_complete": False
    }

    if not user or not user.is_authenticated:
        return capabilities

    # 1. Determine base role matching
    is_client_owner = (order.client_id == user.id)

    provider_profile = getattr(user, "provider_profile", None)
    is_assigned_provider = (
        provider_profile is not None and 
        order.provider_profile_id == provider_profile.id
    )

    # 2. Staff policy: Staff users who are not actual participants (client or provider)
    # receive all capability flags as False. If they are the client or provider,
    # they follow normal rules.
    if getattr(user, "is_staff", False):
        if not is_client_owner and not is_assigned_provider:
            return capabilities

    # 3. Calculate status and payment status based capabilities
    is_paid = (order.payment_status == Order.PaymentStatus.PAID)
    is_confirmed = (order.status == Order.Status.CONFIRMED)
    is_in_progress = (order.status == Order.Status.IN_PROGRESS)

    can_generate_start = is_client_owner and is_paid and is_confirmed
    can_generate_finish = is_client_owner and is_paid and is_in_progress
    can_check_in = is_assigned_provider and is_paid and is_confirmed
    can_complete = is_assigned_provider and is_paid and is_in_progress

    capabilities.update({
        "is_client_owner": is_client_owner,
        "is_assigned_provider": is_assigned_provider,
        "can_generate_start": can_generate_start,
        "can_generate_finish": can_generate_finish,
        "can_check_in": can_check_in,
        "can_complete": can_complete
    })

    return capabilities
