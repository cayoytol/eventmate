from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from .models import Payment, PaymentTransaction
from .serializers import (
    PaymentSerializer, CreatePaymentSerializer,
    CreatePaymentResponseSerializer, PaymentStatusResponseSerializer
)
from .permissions import IsPaymentOwner
from apps.billing.models import Subscription
from apps.billing.permissions import IsProviderAuthenticated
from apps.accounts.permissions import IsNotBlockedProvider
from apps.marketplace.models import Order
from .adapters import get_payment_adapter
import uuid
import logging
from apps.payments.providers.paypal.client import get_paypal_orders_client
from apps.payments.exceptions import (
    PaymentProviderConfigurationError,
    PaymentProviderResponseError,
    PaymentProviderTemporaryError
)
from apps.payments.services import MarketplaceCheckoutService
from rest_framework.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


class PaymentViewSet(viewsets.GenericViewSet):
    """Mock payment endpoints"""
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsProviderAuthenticated]
    
    def get_permissions(self):
        if self.action == 'mark_paid':
            return [permissions.IsAuthenticated(), IsProviderAuthenticated(), IsPaymentOwner()]
        if self.action == 'create_payment':
            return [permissions.IsAuthenticated(), IsProviderAuthenticated(), IsNotBlockedProvider()]
        return super().get_permissions()
    
    @action(detail=False, methods=['post'], url_path='create')
    def create_payment(self, request):
        """Create a pending payment for subscription"""
        serializer = CreatePaymentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        subscription_id = serializer.validated_data['subscription_id']
        
        with transaction.atomic():
            # Load subscription with plan for checks
            try:
                subscription = Subscription.objects.select_related('plan').get(id=subscription_id)
            except Subscription.DoesNotExist:
                return Response(
                    {"detail": "Subscription not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            provider_profile = request.user.provider_profile
            
            # Security: check subscription ownership
            if subscription.provider_profile != provider_profile:
                return Response(
                    {"detail": "You cannot create payment for someone else's subscription"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Business logic: no payment for free plan
            if subscription.plan.price == 0:
                return Response(
                    {"detail": "Free plan does not require payment"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Business logic: subscription must be inactive
            if subscription.is_active:
                return Response(
                    {"detail": "Subscription is already active"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Business logic: prevent duplicate payment
            if subscription.payments.filter(status=Payment.Status.PAID).exists():
                return Response(
                    {"detail": "Subscription already has a successful payment"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create payment
            payment = Payment.objects.create(
                provider_profile=provider_profile,
                subscription=subscription,
                amount=subscription.plan.price,
                currency='KZT',
                status=Payment.Status.PENDING
            )
        
        result_serializer = PaymentSerializer(payment)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'], url_path='mark-paid')
    def mark_paid(self, request, pk=None):
        """Mark payment as paid (mock confirmation)"""
        payment = self.get_object()
        
        if payment.status != Payment.Status.PENDING:
            return Response(
                {"detail": "Payment is not pending"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            payment.mark_as_paid()
        
        serializer = PaymentSerializer(payment)
        return Response(serializer.data)


class OrderPaymentQuoteView(APIView):
    """Non-mutating preview of order payment amounts and currency conversion."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id):
        user = request.user

        # Only clients can quote order payments
        if not hasattr(user, 'role') or user.role != 'client':
            return Response(
                {"detail": "Only clients can view order payment quotes."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        # Ownership check
        if order.client_id != user.id:
            return Response(
                {"detail": "You do not have permission to view this order quote."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Eligibility check
        if order.status != Order.Status.CONFIRMED:
            return Response(
                {"detail": f"Order is {order.status}. Only CONFIRMED orders can be quoted."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if order.payment_status == Order.PaymentStatus.PAID:
            return Response(
                {"detail": "Order has already been paid."},
                status=status.HTTP_400_BAD_REQUEST
            )

        active_provider = getattr(settings, "PAYMENT_PROVIDER", "mock").lower()

        # Calculate quote amounts (no DB mutation, no PayPal API call)
        original_amount = order.price_agreed
        original_currency = 'KZT'
        provider_amount = original_amount
        provider_currency = original_currency
        conversion_rate = Decimal('1.00')
        conversion_source = 'direct'

        if active_provider == 'paypal':
            conversion_enabled = getattr(settings, 'PAYPAL_SANDBOX_CONVERSION_ENABLED', True)
            if conversion_enabled:
                rate = getattr(settings, 'PAYPAL_SANDBOX_KZT_PER_USD', Decimal('450.00'))
                if isinstance(rate, (int, float)):
                    rate = Decimal(str(rate))
                if rate > 0:
                    from decimal import ROUND_HALF_UP
                    provider_amount = (original_amount / rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    provider_currency = getattr(settings, 'PAYPAL_SANDBOX_CURRENCY', 'USD')
                    conversion_rate = rate
                    conversion_source = 'paypal_sandbox_fixed'

        return Response({
            "order_id": order.id,
            "original_amount": str(original_amount),
            "original_currency": original_currency,
            "provider_amount": str(provider_amount),
            "provider_currency": provider_currency,
            "conversion_rate": str(conversion_rate),
            "conversion_source": conversion_source,
            "active_provider": active_provider,
        })


class CreateOrderPaymentView(APIView):
    """Create a pending payment transaction for a confirmed order"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        user = request.user
        
        # Authenticated clients only
        if not hasattr(user, 'role') or user.role != 'client':
            return Response(
                {"detail": "Only clients can create order payments."},
                status=status.HTTP_403_FORBIDDEN
            )

        active_provider = getattr(settings, "PAYMENT_PROVIDER", "mock").lower()

        try:
            tx, is_initializing, retry_after, action = MarketplaceCheckoutService.get_or_create_checkout(order_id, user)
            
            if is_initializing:
                return Response(
                    {
                        "code": "checkout_initializing",
                        "provider": active_provider,
                        "transaction_id": str(tx.id),
                        "retry_after": retry_after
                    },
                    status=status.HTTP_202_ACCEPTED
                )

            # Success
            serializer = CreatePaymentResponseSerializer(tx)
            status_code = status.HTTP_201_CREATED if action == "new" else status.HTTP_200_OK
            return Response(serializer.data, status=status_code)

        except PaymentProviderConfigurationError as e:
            return Response(
                {
                    "code": "payment_provider_unavailable",
                    "provider": active_provider,
                    "retryable": True,
                    "detail": "Payment provider is not available. Please contact support."
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except PaymentProviderTemporaryError as e:
            return Response(
                {
                    "code": "paypal_temporarily_unavailable",
                    "provider": active_provider,
                    "retryable": True,
                    "detail": "Payment provider temporarily unavailable. Please try again."
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except PaymentProviderResponseError as e:
            return Response(
                {
                    "detail": f"Payment initialization failed: {str(e)}"
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except PermissionDenied as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected checkout creation failure: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Internal server error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OrderPaymentStatusView(APIView):
    """Retrieve order payment status and latest transaction details"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id):
        user = request.user
        
        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Access check: Client owner, Provider of the order, or staff/admin
        is_client = (order.client_id == user.id)
        is_provider = (hasattr(user, 'provider_profile') and order.provider_profile == user.provider_profile)
        is_staff = getattr(user, 'is_staff', False)

        if not (is_client or is_provider or is_staff):
            return Response(
                {"detail": "You do not have permission to view this order payment status."},
                status=status.HTTP_403_FORBIDDEN
            )

        latest_tx = PaymentTransaction.objects.filter(order=order).order_by('-created_at').first()
        active_provider = getattr(settings, "PAYMENT_PROVIDER", "mock").lower()

        # Find active transaction
        active_tx = PaymentTransaction.objects.filter(
            order=order,
            provider=active_provider,
            status=PaymentTransaction.Status.PENDING
        ).first()

        if not active_tx:
            active_tx = PaymentTransaction.objects.filter(
                order=order,
                provider=active_provider
            ).order_by('-created_at').first()

        # Calculate coordinates
        is_initializing = False
        can_continue = False
        can_retry = False

        if order.payment_status != Order.PaymentStatus.PAID:
            if order.status == Order.Status.CONFIRMED:
                if not active_tx:
                    can_retry = True
                else:
                    if active_tx.status in [PaymentTransaction.Status.FAILED, PaymentTransaction.Status.CANCELLED]:
                        can_retry = True
                    elif active_tx.status == PaymentTransaction.Status.PENDING:
                        if active_tx.checkout_state == PaymentTransaction.CheckoutState.RETRYABLE_ERROR:
                            can_retry = True
                        elif active_tx.checkout_state == PaymentTransaction.CheckoutState.INITIALIZING:
                            is_initializing = True
                        elif active_tx.checkout_state == PaymentTransaction.CheckoutState.READY and active_tx.checkout_url:
                            can_continue = True

        if active_tx:
            active_tx.can_continue = can_continue
            active_tx.can_retry = can_retry
            active_tx.is_initializing = is_initializing

        # Check provider availability
        provider_available = True
        if active_provider == "paypal":
            client_id = getattr(settings, 'PAYPAL_ORDERS_CLIENT_ID', '')
            client_secret = getattr(settings, 'PAYPAL_ORDERS_CLIENT_SECRET', '')
            provider_available = bool(client_id and client_secret)

        provider_mode = getattr(settings, "PAYPAL_MODE", "sandbox") if active_provider == "paypal" else "sandbox"

        data = {
            "order_id": order.id,
            "order_payment_status": order.payment_status,
            "latest_transaction": latest_tx,
            "active_transaction": active_tx,
            "active_provider": active_provider,
            "provider_mode": provider_mode,
            "provider_available": provider_available
        }

        serializer = PaymentStatusResponseSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PaymentWebhookView(APIView):
    """Public webhook callback for payment confirmations"""
    permission_classes = [permissions.AllowAny]

    def post(self, request, provider):
        provider_name = provider.lower()
        active_provider = getattr(settings, "PAYMENT_PROVIDER", "mock").lower()
        if provider_name != active_provider:
            return Response(
                {"detail": f"Provider '{provider}' is not active or unknown."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            adapter = get_payment_adapter()
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Verify signature through adapter (outside database lock!)
        if not adapter.verify_webhook(request):
            return Response({"detail": "Invalid webhook signature."}, status=status.HTTP_400_BAD_REQUEST)

        # Parse payload through adapter (outside database lock!)
        payload = request.data
        try:
            parsed = adapter.parse_webhook_payload(payload)
        except Exception as e:
            return Response({"detail": f"Failed to parse payload: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        webhook_status = parsed.get("status")
        if webhook_status not in ["success", "failed", "cancelled", "pending"]:
            return Response({"detail": f"Invalid webhook status: {webhook_status}"}, status=status.HTTP_400_BAD_REQUEST)

        tx_id = parsed.get("transaction_id")
        provider_ref = parsed.get("provider_reference")
        invoice_id = parsed.get("invoice_id")

        # Phase B: Find transaction first without lock to get order_id
        transaction_obj = None
        if tx_id:
            transaction_obj = PaymentTransaction.objects.filter(id=tx_id, provider=provider_name).first()
        if not transaction_obj and provider_ref:
            transaction_obj = PaymentTransaction.objects.filter(
                provider=provider_name,
                provider_reference=provider_ref
            ).first()
        if not transaction_obj and invoice_id:
            try:
                uuid.UUID(str(invoice_id))
                transaction_obj = PaymentTransaction.objects.filter(id=invoice_id, provider=provider_name).first()
            except (ValueError, TypeError):
                pass
            if not transaction_obj:
                transaction_obj = PaymentTransaction.objects.filter(
                    order_id=invoice_id,
                    provider=provider_name
                ).order_by('-created_at').first()

        if not transaction_obj:
            return Response({"detail": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)

        # Phase C: Lock parent Order first, child PaymentTransaction second
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=transaction_obj.order_id)
            transaction_obj = PaymentTransaction.objects.select_for_update().get(pk=transaction_obj.pk)

            # Amount and currency checks
            try:
                parsed_amount = Decimal(str(parsed.get("amount")))
            except (ValueError, TypeError, InvalidOperation):
                return Response({"detail": "Invalid amount format in payload."}, status=status.HTTP_400_BAD_REQUEST)

            expected_amount = transaction_obj.provider_amount if transaction_obj.provider_amount is not None else transaction_obj.amount
            expected_currency = transaction_obj.provider_currency if transaction_obj.provider_currency else transaction_obj.currency

            if parsed_amount != expected_amount:
                return Response({"detail": "Transaction amount mismatch."}, status=status.HTTP_400_BAD_REQUEST)

            if parsed.get("currency") != expected_currency:
                return Response({"detail": "Transaction currency mismatch."}, status=status.HTTP_400_BAD_REQUEST)

            # Check idempotency
            if transaction_obj.status == PaymentTransaction.Status.SUCCESS:
                if provider_name == 'cloudpayments':
                    return Response({"code": 0}, status=status.HTTP_200_OK)
                return Response({
                    "ok": True,
                    "status": transaction_obj.status,
                    "transaction_id": transaction_obj.id
                }, status=status.HTTP_200_OK)

            if transaction_obj.status in [PaymentTransaction.Status.FAILED, PaymentTransaction.Status.CANCELLED]:
                if provider_name == 'cloudpayments':
                    return Response({"code": 0}, status=status.HTTP_200_OK)
                return Response({
                    "ok": True,
                    "status": transaction_obj.status,
                    "transaction_id": transaction_obj.id
                }, status=status.HTTP_200_OK)

            # Handle pending state update
            if webhook_status == "pending":
                transaction_obj.provider_payment_id = parsed.get("provider_payment_id", transaction_obj.provider_payment_id)
                transaction_obj.provider_reference = parsed.get("provider_reference", transaction_obj.provider_reference)
                transaction_obj.raw_response = parsed.get("raw_response", transaction_obj.raw_response)
                transaction_obj.save()
                if provider_name == 'cloudpayments':
                    return Response({"code": 0}, status=status.HTTP_200_OK)
                return Response({
                    "ok": True,
                    "status": transaction_obj.status,
                    "transaction_id": transaction_obj.id
                }, status=status.HTTP_200_OK)

            # Update statuses
            if webhook_status == "success":
                try:
                    transaction_obj = MarketplaceCheckoutService.complete_payment(
                        transaction_id=str(transaction_obj.id),
                        provider_payment_id=parsed.get("provider_payment_id") or transaction_obj.provider_payment_id,
                        provider_reference=parsed.get("provider_reference") or transaction_obj.provider_reference,
                        raw_response=parsed.get("raw_response") or transaction_obj.raw_response
                    )
                except ValueError as e:
                    return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
                    
            elif webhook_status in ["failed", "cancelled"]:
                status_map = {
                    "failed": PaymentTransaction.Status.FAILED,
                    "cancelled": PaymentTransaction.Status.CANCELLED
                }
                transaction_obj.status = status_map[webhook_status]
                transaction_obj.checkout_state = PaymentTransaction.CheckoutState.TERMINAL_ERROR
                transaction_obj.provider_payment_id = parsed.get("provider_payment_id", transaction_obj.provider_payment_id)
                transaction_obj.provider_reference = parsed.get("provider_reference", transaction_obj.provider_reference)
                transaction_obj.raw_response = parsed.get("raw_response", transaction_obj.raw_response)
                transaction_obj.save()
                
                if order.payment_status != Order.PaymentStatus.PAID:
                    order.payment_status = Order.PaymentStatus.FAILED
                    order.save(update_fields=['payment_status'])

        if provider_name == 'cloudpayments':
            return Response({"code": 0}, status=status.HTTP_200_OK)

        return Response({
            "ok": True,
            "status": transaction_obj.status,
            "transaction_id": transaction_obj.id
        }, status=status.HTTP_200_OK)


from django.shortcuts import redirect

class PayPalOrderReturnView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        token = request.query_params.get("token")
        transaction_id = request.query_params.get("transaction_id")
        
        order_id = ""
        if transaction_id:
            try:
                tx = PaymentTransaction.objects.get(id=transaction_id)
                order_id = tx.order_id
            except Exception:
                pass
                
        base_url = settings.PAYMENT_RETURN_URL
        if order_id:
            redirect_url = base_url.replace("{order_id}", str(order_id))
        else:
            redirect_url = base_url.replace("/orders/{order_id}/", "/orders/")
            
        connector = '&' if '?' in redirect_url else '?'
        if token and transaction_id:
            redirect_url = f"{redirect_url}{connector}transaction_id={transaction_id}&token={token}&status=success"
        else:
            redirect_url = f"{redirect_url}{connector}status=cancel"
            
        return redirect(redirect_url)


class PayPalOrderCaptureView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        paypal_order_id = request.data.get("paypal_order_id")
        if not paypal_order_id:
            return Response({"detail": "paypal_order_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Phase B: Find transaction first without lock
        try:
            transaction_obj = PaymentTransaction.objects.select_related('order').get(
                provider_payment_id=paypal_order_id,
                provider='paypal'
            )
        except PaymentTransaction.DoesNotExist:
            return Response({"detail": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check ownership and token validation (custom_id)
        if transaction_obj.order.client_id != request.user.id:
            return Response({"detail": "You do not own this transaction."}, status=status.HTTP_403_FORBIDDEN)

        # Idempotent success check
        if transaction_obj.status == PaymentTransaction.Status.SUCCESS:
            return Response({
                "status": "success",
                "payment_status": "paid",
                "transaction_id": transaction_obj.id
            })

        client = get_paypal_orders_client()

        # Call PayPal GET Order outside database transaction
        try:
            order_data = client.get_order(paypal_order_id)
        except Exception as e:
            return Response({"detail": f"Failed to retrieve PayPal order: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate custom_id prefix and value
        purchase_units = order_data.get("purchase_units", [])
        if not purchase_units:
            return Response({"detail": "PayPal order has no purchase units."}, status=status.HTTP_400_BAD_REQUEST)

        custom_id = purchase_units[0].get("custom_id", "")
        if custom_id != f"marketplace-payment-{transaction_obj.id}":
            return Response({"detail": "PayPal order custom ID mismatch."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate snapshot amount & currency
        paypal_amount = purchase_units[0].get("amount", {}).get("value")
        paypal_currency = purchase_units[0].get("amount", {}).get("currency_code")

        if Decimal(str(paypal_amount)) != transaction_obj.provider_amount:
            return Response({"detail": "Payment amount mismatch."}, status=status.HTTP_400_BAD_REQUEST)
        if paypal_currency != transaction_obj.provider_currency:
            return Response({"detail": "Payment currency mismatch."}, status=status.HTTP_400_BAD_REQUEST)

        # Call capture outside database transaction
        paypal_status = order_data.get("status")
        capture_id = ""
        capture_status = ""

        if paypal_status == "APPROVED":
            try:
                cap_resp = client.capture_order(paypal_order_id, f"paypal-order-capture-{transaction_obj.id}")
                paypal_status = cap_resp.get("status")
                p_units_resp = cap_resp.get("purchase_units", [])
                if p_units_resp:
                    captures = p_units_resp[0].get("payments", {}).get("captures", [])
                    if captures:
                        capture_id = captures[0].get("id", "")
                        capture_status = captures[0].get("status", "")
            except Exception as e:
                return Response({"detail": f"PayPal capture call failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        elif paypal_status == "COMPLETED":
            p_units_resp = order_data.get("purchase_units", [])
            if p_units_resp:
                captures = p_units_resp[0].get("payments", {}).get("captures", [])
                if captures:
                    capture_id = captures[0].get("id", "")
                    capture_status = captures[0].get("status", "")

        # Phase C: Apply state changes with row locks using centralized complete_payment
        if paypal_status == "COMPLETED" or capture_status == "COMPLETED":
            try:
                raw_resp = {
                    "paypal_order_id": paypal_order_id,
                    "paypal_capture_id": capture_id,
                    "order_status": paypal_status,
                    "capture_status": capture_status or "COMPLETED",
                    "custom_id": custom_id,
                    "sandbox": (getattr(settings, 'PAYPAL_MODE', 'sandbox') == 'sandbox')
                }
                transaction_obj = MarketplaceCheckoutService.complete_payment(
                    transaction_id=str(transaction_obj.id),
                    provider_payment_id=paypal_order_id,
                    provider_reference=capture_id or paypal_order_id,
                    raw_response=raw_resp
                )
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                "status": "success",
                "payment_status": "paid",
                "transaction_id": transaction_obj.id
            })
        else:
            return Response({"detail": f"PayPal order status is {paypal_status}. Only COMPLETED capture is allowed."}, status=status.HTTP_400_BAD_REQUEST)

