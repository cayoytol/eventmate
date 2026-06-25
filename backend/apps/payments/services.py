import uuid
import logging
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.conf import settings
from rest_framework.exceptions import PermissionDenied

from apps.marketplace.models import Order
from apps.payments.models import PaymentTransaction
from apps.payments.exceptions import (
    PaymentProviderError,
    PaymentProviderConfigurationError,
    PaymentProviderResponseError,
    PaymentProviderTemporaryError
)
from apps.payments.url_helpers import validate_paypal_approval_url, extract_paypal_approval_url
from apps.payments.providers.paypal.client import get_paypal_orders_client
from apps.payments.adapters import get_payment_adapter

logger = logging.getLogger(__name__)

class MarketplaceCheckoutService:
    @staticmethod
    def reserve_checkout(order_id: int, user, active_provider: str) -> tuple:
        """
        Phase A: Database Reservation.
        Locks parent Order first. Finds or creates the provider-specific pending PaymentTransaction.
        Saves immutable snapshots and commits.
        Returns (transaction, action_type, attempt_token)
        """
        # Ensure provider is allowed
        if active_provider not in ['mock', 'paypal', 'cloudpayments']:
            raise ValueError(f"Unsupported payment provider: {active_provider}")

        # Verify configuration before reservation
        try:
            get_payment_adapter()
        except PaymentProviderConfigurationError:
            raise

        try:
            with transaction.atomic():
                # Lock parent Order first
                try:
                    order = Order.objects.select_for_update().get(pk=order_id)
                except Order.DoesNotExist:
                    raise ValueError("Order not found.")

                # Ownership and eligibility checks
                if order.client_id != user.id:
                    raise PermissionDenied("You do not have permission to pay for this order.")
                if order.status != Order.Status.CONFIRMED:
                    raise ValueError(f"Order status is {order.status}. Only CONFIRMED orders can be paid.")
                if order.payment_status == Order.PaymentStatus.PAID:
                    raise ValueError("Order has already been paid.")

                # Look up existing pending transaction
                existing_tx = PaymentTransaction.objects.select_for_update().filter(
                    order=order,
                    provider=active_provider,
                    status=PaymentTransaction.Status.PENDING
                ).first()

                if existing_tx:
                    # Check if Order amount or currency has mutated
                    if not existing_tx.matches_order_payable_snapshot(order):
                        # Expire the old transaction
                        existing_tx.status = PaymentTransaction.Status.FAILED
                        existing_tx.checkout_state = PaymentTransaction.CheckoutState.TERMINAL_ERROR
                        existing_tx.checkout_error_code = 'order_amount_changed'
                        existing_tx.checkout_error_at = timezone.now()
                        existing_tx.save(update_fields=['status', 'checkout_state', 'checkout_error_code', 'checkout_error_at'])
                        existing_tx = None

                if existing_tx:
                    state = existing_tx.checkout_state
                    
                    # Fast Path: Ready checkout
                    if state == PaymentTransaction.CheckoutState.READY:
                        if existing_tx.checkout_url and existing_tx.provider_payment_id:
                            try:
                                if active_provider == "paypal":
                                    validate_paypal_approval_url(existing_tx.checkout_url)
                                return existing_tx, "ready", existing_tx.checkout_initialization_token
                            except ValueError:
                                # Invalid url, recover/re-initialize
                                pass

                    # Fresh initialization concurrency check
                    if state == PaymentTransaction.CheckoutState.INITIALIZING:
                        timeout = getattr(settings, 'PAYPAL_CHECKOUT_INITIALIZATION_TIMEOUT_SECONDS', 300)
                        now = timezone.now()
                        started_at = existing_tx.checkout_initialization_started_at
                        if started_at and (now - started_at).total_seconds() < timeout:
                            return existing_tx, "initializing", existing_tx.checkout_initialization_token

                    # Stale reclaim or retryable/idle: Reclaim with new token
                    attempt_token = uuid.uuid4()
                    existing_tx.checkout_state = PaymentTransaction.CheckoutState.INITIALIZING
                    existing_tx.checkout_initialization_token = attempt_token
                    existing_tx.checkout_initialization_started_at = timezone.now()
                    existing_tx.save(update_fields=['checkout_state', 'checkout_initialization_token', 'checkout_initialization_started_at'])
                    return existing_tx, "reclaim", attempt_token

                # Create a new transaction with immutable financial snapshots
                rate = Decimal("1.00")
                provider_currency = 'KZT'
                provider_amount = order.price_agreed
                conversion_source = 'direct'

                if active_provider == 'paypal':
                    conversion_enabled = getattr(settings, 'PAYPAL_SANDBOX_CONVERSION_ENABLED', True)
                    if conversion_enabled:
                        if getattr(settings, 'PAYPAL_MODE', 'sandbox') != 'sandbox':
                            raise ValueError("Fixed sandbox currency conversion is only allowed when PAYPAL_MODE=sandbox.")
                        rate = getattr(settings, 'PAYPAL_SANDBOX_KZT_PER_USD', Decimal("450.00"))
                        if rate <= 0:
                            raise ValueError("Conversion rate must be positive.")
                        provider_currency = getattr(settings, 'PAYPAL_SANDBOX_CURRENCY', 'USD')
                        provider_amount = (order.price_agreed / rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        if provider_amount <= Decimal("0.00"):
                            raise ValueError("Converted provider amount rounds to 0.00. Purchase amount is too low.")
                        conversion_source = 'paypal_sandbox_fixed'

                attempt_token = uuid.uuid4()
                transaction_obj = PaymentTransaction.objects.create(
                    order=order,
                    provider=active_provider,
                    amount=order.price_agreed,
                    currency='KZT',
                    status=PaymentTransaction.Status.PENDING,
                    checkout_state=PaymentTransaction.CheckoutState.INITIALIZING,
                    checkout_initialization_token=attempt_token,
                    checkout_initialization_started_at=timezone.now(),
                    idempotency_key=f"order_{order.id}_prov_{active_provider}_{uuid.uuid4()}",
                    provider_amount=provider_amount,
                    provider_currency=provider_currency,
                    conversion_rate=rate,
                    conversion_source=conversion_source,
                    conversion_locked_at=timezone.now()
                )
                return transaction_obj, "new", attempt_token

        except IntegrityError:
            # Concurrent insert recovery
            with transaction.atomic():
                existing_tx = PaymentTransaction.objects.filter(
                    order_id=order_id,
                    provider=active_provider,
                    status=PaymentTransaction.Status.PENDING
                ).select_for_update().first()
                if existing_tx:
                    state = existing_tx.checkout_state
                    if state == PaymentTransaction.CheckoutState.READY:
                        return existing_tx, "ready", existing_tx.checkout_initialization_token
                    return existing_tx, "initializing", existing_tx.checkout_initialization_token
                raise

    @staticmethod
    def perform_provider_operation(transaction_obj: PaymentTransaction, attempt_token: uuid.UUID, active_provider: str) -> dict:
        """
        Phase B: External Provider Operation (OUTSIDE database transactions).
        Calls PayPal create/get endpoints safely using stable Request IDs.
        """
        if active_provider == 'mock':
            checkout_url = settings.PAYMENT_RETURN_URL.replace("{order_id}", str(transaction_obj.order_id)) + f"?status=success&transaction_id={transaction_obj.id}"
            return {
                'checkout_url': checkout_url,
                'provider_payment_id': f"mock-{transaction_obj.id}",
                'raw_response': {'status': 'CREATED'}
            }

        if active_provider == 'paypal':
            client = get_paypal_orders_client()
            provider_payment_id = transaction_obj.provider_payment_id

            if provider_payment_id:
                # Recovery Mode: Recover existing PayPal Order details
                try:
                    resp = client.get_order(provider_payment_id)
                except Exception as e:
                    logger.error(f"PayPal GET Order failed: {str(e)}")
                    raise PaymentProviderTemporaryError("paypal_timeout")

                purchase_units = resp.get("purchase_units", [])
                if not purchase_units:
                    raise PaymentProviderResponseError("paypal_invalid_response")

                custom_id = purchase_units[0].get("custom_id", "")
                if custom_id != f"marketplace-payment-{transaction_obj.id}":
                    raise PaymentProviderResponseError("paypal_invalid_response")

                # Validate amounts
                paypal_amount = purchase_units[0].get("amount", {}).get("value")
                paypal_currency = purchase_units[0].get("amount", {}).get("currency_code")
                if Decimal(str(paypal_amount)) != transaction_obj.provider_amount or paypal_currency != transaction_obj.provider_currency:
                    raise PaymentProviderResponseError("paypal_invalid_response")

                paypal_status = resp.get("status")
                if paypal_status in ["VOIDED", "COMPLETED"]:
                    raise PaymentProviderResponseError("paypal_terminal_order_state")

                try:
                    approve_url = extract_paypal_approval_url(resp.get("links", []))
                except ValueError:
                    raise PaymentProviderResponseError("paypal_approve_url_missing")

                return {
                    'checkout_url': approve_url,
                    'provider_payment_id': provider_payment_id,
                    'raw_response': {
                        "paypal_order_id": provider_payment_id,
                        "paypal_capture_id": "",
                        "order_status": paypal_status,
                        "capture_status": "",
                        "custom_id": custom_id,
                        "sandbox": (getattr(settings, 'PAYPAL_MODE', 'sandbox') == 'sandbox')
                    }
                }
            else:
                # Creation Mode: Create fresh PayPal Order
                base_return_url = settings.PAYMENT_RETURN_URL.replace("{order_id}", str(transaction_obj.order_id))
                connector = '&' if '?' in base_return_url else '?'
                return_url = f"{base_return_url}{connector}transaction_id={transaction_obj.id}&status=success"
                cancel_url = settings.PAYMENT_CANCEL_URL.replace("{order_id}", str(transaction_obj.order_id)) + f"{connector}transaction_id={transaction_obj.id}&status=cancel"

                payload = {
                    "intent": "CAPTURE",
                    "purchase_units": [{
                        "amount": {
                            "currency_code": str(transaction_obj.provider_currency),
                            "value": str(transaction_obj.provider_amount)
                        },
                        "custom_id": f"marketplace-payment-{transaction_obj.id}",
                        "description": f"Marketplace Order #{transaction_obj.order_id}"
                    }],
                    "application_context": {
                        "return_url": return_url,
                        "cancel_url": cancel_url,
                        "user_action": "PAY_NOW"
                    }
                }

                request_id = f"paypal-order-create-{transaction_obj.id}"
                try:
                    resp = client.create_order(payload, request_id)
                except Exception as e:
                    logger.error(f"PayPal create_order HTTP failure: {str(e)}")
                    raise PaymentProviderTemporaryError("paypal_temporarily_unavailable")

                order_id = resp.get("id")
                if not order_id:
                    raise PaymentProviderResponseError("paypal_invalid_response")

                try:
                    approve_url = extract_paypal_approval_url(resp.get("links", []))
                except ValueError:
                    raise PaymentProviderResponseError("paypal_approve_url_missing")

                raw_response = {
                    "paypal_order_id": order_id,
                    "paypal_capture_id": "",
                    "order_status": resp.get("status"),
                    "capture_status": "",
                    "custom_id": f"marketplace-payment-{transaction_obj.id}",
                    "sandbox": (getattr(settings, 'PAYPAL_MODE', 'sandbox') == 'sandbox')
                }

                return {
                    'checkout_url': approve_url,
                    'provider_payment_id': order_id,
                    'raw_response': raw_response
                }

        raise ValueError("Unsupported payment provider.")

    @staticmethod
    def apply_provider_result(transaction_id: str, attempt_token: uuid.UUID, provider_result: dict = None, error: Exception = None):
        """
        Phase C: Database Application.
        Locks parent Order first, and child PaymentTransaction second.
        Applies results idempotently ONLY if attempt_token still matches.
        """
        with transaction.atomic():
            # Get transaction first (without lock) to resolve Order PK
            try:
                tx_info = PaymentTransaction.objects.get(pk=transaction_id)
            except PaymentTransaction.DoesNotExist:
                return

            # Lock parent Order first
            Order.objects.select_for_update().get(pk=tx_info.order_id)

            # Lock PaymentTransaction second
            tx = PaymentTransaction.objects.select_for_update().get(pk=transaction_id)

            # Attempt token validation check (avoid stale overwrite races)
            if tx.checkout_initialization_token != attempt_token:
                logger.warning(f"Discarding stale checkout reservation results for tx {transaction_id}")
                return tx

            if error:
                safe_error_code = "internal_error"
                if isinstance(error, PaymentProviderError):
                    allowed_codes = [
                        "paypal_timeout",
                        "paypal_temporarily_unavailable",
                        "paypal_invalid_response",
                        "paypal_approve_url_missing",
                        "paypal_terminal_order_state"
                    ]
                    msg = str(error)
                    if msg in allowed_codes:
                        safe_error_code = msg

                if isinstance(error, PaymentProviderTemporaryError):
                    tx.checkout_state = PaymentTransaction.CheckoutState.RETRYABLE_ERROR
                    tx.checkout_error_code = safe_error_code
                    tx.checkout_error_at = timezone.now()
                    tx.checkout_retry_after = 2
                else:
                    tx.status = PaymentTransaction.Status.FAILED
                    tx.checkout_state = PaymentTransaction.CheckoutState.TERMINAL_ERROR
                    tx.checkout_error_code = safe_error_code
                    tx.checkout_error_at = timezone.now()
                tx.save()
                return tx

            # Succeeded
            tx.checkout_url = provider_result['checkout_url']
            tx.provider_payment_id = provider_result['provider_payment_id']
            tx.provider_reference = provider_result['provider_payment_id']
            tx.raw_response = provider_result['raw_response']
            tx.checkout_state = PaymentTransaction.CheckoutState.READY
            tx.checkout_error_code = ""
            tx.checkout_error_at = None
            tx.checkout_retry_after = None
            tx.save()
            return tx

    @classmethod
    def get_or_create_checkout(cls, order_id: int, user) -> tuple:
        """
        Main orchestration service helper.
        Returns (PaymentTransaction, is_initializing, retry_after, action)
        """
        active_provider = getattr(settings, "PAYMENT_PROVIDER", "mock").lower()

        # Step 1: Phase A - Reserve
        tx, action, token = cls.reserve_checkout(order_id, user, active_provider)

        if action == "ready":
            return tx, False, 0, action

        if action == "initializing":
            # Another worker owns this fresh initialization - genuinely wait
            return tx, True, 2, action

        # We own the initialization (action='new' or 'reclaim')
        # Step 2: Phase B (outside DB transaction) - synchronous provider call
        provider_result = None
        error = None
        try:
            provider_result = cls.perform_provider_operation(tx, token, active_provider)
        except Exception as e:
            error = e

        # Step 3: Phase C - Apply result
        updated_tx = cls.apply_provider_result(tx.id, token, provider_result=provider_result, error=error)

        # Since WE owned this init, we know the result synchronously
        if error:
            # Re-raise to let the view return the correct HTTP status
            if isinstance(error, PaymentProviderConfigurationError):
                raise error
            if isinstance(error, PaymentProviderTemporaryError):
                raise error
            # Other errors (e.g. PaymentProviderResponseError)
            raise PaymentProviderResponseError(str(error))

        return updated_tx, False, 0, action

    @staticmethod
    def complete_payment(transaction_id: str, provider_payment_id: str, provider_reference: str, raw_response: dict) -> PaymentTransaction:
        """
        Unified idempotent completion logic.
        Locks Order first, locks PaymentTransaction second.
        """
        with transaction.atomic():
            # Get transaction without locking first to get order_id
            try:
                tx_info = PaymentTransaction.objects.get(pk=transaction_id)
            except PaymentTransaction.DoesNotExist:
                raise ValueError("Transaction not found.")

            # Lock parent Order first
            order = Order.objects.select_for_update().get(pk=tx_info.order_id)

            # Lock PaymentTransaction second
            tx = PaymentTransaction.objects.select_for_update().get(pk=transaction_id)

            # verify provider is paypal (with mock and cloudpayments fallbacks for tests)
            if tx.provider not in ['paypal', 'mock', 'cloudpayments']:
                raise ValueError(f"Provider mismatch: expected 'paypal', got '{tx.provider}'")

            # verify transaction belongs to the Order
            if tx.order_id != order.id:
                raise ValueError("Transaction does not belong to the order.")

            # verify transaction is not failed or cancelled
            if tx.status in [PaymentTransaction.Status.FAILED, PaymentTransaction.Status.CANCELLED]:
                raise ValueError("Cannot complete a failed or cancelled transaction.")

            # return safely when already successful
            if tx.status == PaymentTransaction.Status.SUCCESS:
                return tx

            # validate provider payment/order identity
            if tx.provider == 'paypal':
                if tx.provider_payment_id and tx.provider_payment_id != provider_payment_id:
                    raise ValueError("Provider payment ID mismatch.")

            # update PaymentTransaction to success once
            tx.status = PaymentTransaction.Status.SUCCESS
            tx.checkout_state = PaymentTransaction.CheckoutState.COMPLETED
            tx.checkout_url = ""  # clear checkout URL exposure
            tx.paid_at = timezone.now()
            tx.provider_payment_id = provider_payment_id
            tx.provider_reference = provider_reference
            tx.raw_response = raw_response
            tx.save()

            # update Order.payment_status to paid once
            if order.payment_status != Order.PaymentStatus.PAID:
                order.payment_status = Order.PaymentStatus.PAID
                order.save(update_fields=['payment_status'])

                # trigger notifications once
                from apps.notifications.services import create_notification as safe_create_notification
                from apps.notifications.models import Notification as NotificationModel

                safe_create_notification(
                    user=order.client,
                    title="Заказ оплачен",
                    message=f"Оплата заказа #{order.id} прошла успешно.",
                    n_type=NotificationModel.NotificationType.ORDER_PAID,
                    metadata={'order_id': order.id}
                )
                safe_create_notification(
                    user=order.provider_profile.user,
                    title="Заказ оплачен",
                    message=f"Заказ #{order.id} успешно оплачен клиентом.",
                    n_type=NotificationModel.NotificationType.ORDER_PAID,
                    metadata={'order_id': order.id}
                )

            return tx
