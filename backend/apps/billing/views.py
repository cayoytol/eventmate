from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsNotBlockedProvider
from .models import Plan, Subscription, PromoCode
from .permissions import IsProviderAuthenticated
from .serializers import (
    PlanSerializer, SubscriptionSerializer, SubscribeSerializer,
    PromoCodeSerializer, PromoCodeValidationSerializer,
    SubscriptionPaymentSerializer, SubscriptionCheckoutSerializer,
    SubscriptionPaymentStatusSerializer, SubscriptionPaymentHistorySerializer
)
from apps.payments.models import Payment
from apps.billing.exceptions import IdempotencyConflictError, PaymentAdapterError
from apps.billing.services.payment_adapters import get_subscription_payment_adapter, BILLING_ADAPTER_REGISTRY
from apps.billing.services.webhooks import process_billing_webhook
from . import services



class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    """Public endpoint for viewing available plans"""
    queryset = Plan.objects.filter(is_active=True)
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]


class BillingViewSet(viewsets.GenericViewSet):
    """Provider billing endpoints"""
    permission_classes = [permissions.IsAuthenticated, IsProviderAuthenticated]
    serializer_class = SubscriptionSerializer
    
    def get_permissions(self):
        if self.action in [
            'subscribe', 'subscription', 'current_subscription', 'validate_promo',
            'mock_activate', 'cancel_subscription', 'checkout', 'payment_status',
            'payment_history'
        ]:
            return [permissions.IsAuthenticated(), IsProviderAuthenticated(), IsNotBlockedProvider()]
        return super().get_permissions()
    
    def _get_subscription_response(self, request):
        provider_profile = request.user.provider_profile
        subscription = services.get_effective_subscription(provider_profile)
        
        active_provider = getattr(settings, 'BILLING_PAYMENT_PROVIDER', 'mock').lower()
        
        if subscription:
            sub_serializer = SubscriptionSerializer(subscription, context={'request': request})
            plan_serializer = PlanSerializer(subscription.plan, context={'request': request})
            entitlements = plan_serializer.data['entitlements']
            
            return Response({
                'subscription': sub_serializer.data,
                'plan': plan_serializer.data,
                'current_plan': plan_serializer.data,  # Backward compatibility
                'entitlements': entitlements,
                'is_fallback': False,
                'active_provider': active_provider
            })
        
        free_plan = services.get_free_plan()
        plan_serializer = PlanSerializer(free_plan, context={'request': request})
        entitlements = plan_serializer.data['entitlements']
        
        return Response({
            'subscription': None,
            'plan': plan_serializer.data,
            'current_plan': plan_serializer.data,  # Backward compatibility
            'entitlements': entitlements,
            'is_fallback': True,
            'active_provider': active_provider
        })
    
    @action(detail=False, methods=['get'])
    def subscription(self, request):
        """Get current active subscription (legacy endpoint)"""
        return self._get_subscription_response(request)
    
    @action(detail=False, methods=['get'], url_path='subscription/current')
    def current_subscription(self, request):
        """Get current active subscription (new endpoint)"""
        return self._get_subscription_response(request)
    
    @action(detail=False, methods=['post'])
    def subscribe(self, request):
        """Deprecated: Please use /api/v1/billing/subscription/checkout/"""
        return Response(
            {"detail": "This endpoint is deprecated. Please use /api/v1/billing/subscription/checkout/ to initiate checkout."},
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=False, methods=['post'], url_path='subscription/checkout')
    def checkout(self, request):
        """Create or reclaim a subscription checkout payment transaction"""
        provider_profile = request.user.provider_profile
        serializer = SubscriptionCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        plan_code = serializer.validated_data['plan_code']
        promo_code_str = serializer.validated_data.get('promo_code')
        
        try:
            plan = Plan.objects.get(code=plan_code, is_active=True)
        except Plan.DoesNotExist:
            return Response({"detail": "Active plan not found"}, status=status.HTTP_404_NOT_FOUND)
            
        idempotency_key = request.headers.get('Idempotency-Key') or request.META.get('HTTP_IDEMPOTENCY_KEY')
        locale = request.META.get('HTTP_ACCEPT_LANGUAGE', 'ru')[:2].lower()
        if locale not in ['ru', 'en', 'kz']:
            locale = 'ru'
            
        try:
            payment, subscription, is_reused = services.create_subscription_checkout(
                provider_profile=provider_profile,
                plan=plan,
                promo_code_str=promo_code_str,
                idempotency_key=idempotency_key,
                locale=locale
            )
        except IdempotencyConflictError as e:
            raise e
        except PaymentAdapterError as e:
            raise e
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            
        if payment.checkout_state == Payment.CheckoutState.INITIALIZING:
            return Response({
                "code": "checkout_initializing",
                "detail": "Checkout is initializing. Please retry or check status.",
                "payment_id": payment.id
            }, status=status.HTTP_202_ACCEPTED)

            
        result_serializer = SubscriptionPaymentSerializer(payment, context={'request': request})
        return Response(result_serializer.data, status=status.HTTP_201_CREATED if not is_reused else status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='subscription/payments')
    def payment_history(self, request):
        """Get paginated billing payments history for the authenticated provider"""
        provider_profile = request.user.provider_profile
        queryset = Payment.objects.filter(provider_profile=provider_profile).order_by('-created_at')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = SubscriptionPaymentHistorySerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
            
        serializer = SubscriptionPaymentHistorySerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path=r'subscription/payments/(?P<payment_id>\d+)/status')
    def payment_status(self, request, payment_id=None):
        """Get the payment transaction status of a specific payment, including entitlement state."""
        provider_profile = request.user.provider_profile
        try:
            payment = Payment.objects.select_related('subscription').get(
                id=payment_id, provider_profile=provider_profile
            )
        except Payment.DoesNotExist:
            return Response({"detail": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = SubscriptionPaymentStatusSerializer(payment, context={'request': request})
        data = serializer.data

        # paid_entitlements_active: True only when payment is paid AND subscription is active
        paid_entitlements_active = False
        if payment.status == Payment.Status.PAID:
            try:
                sub = payment.subscription
                if sub and sub.status == 'active' and sub.start_date and sub.end_date:
                    now = timezone.now()
                    if sub.start_date <= now < sub.end_date:
                        paid_entitlements_active = True
            except Exception:
                pass

        data['paid_entitlements_active'] = paid_entitlements_active

        # Include subscription summary for frontend polling
        try:
            sub = payment.subscription
            if sub:
                data['subscription_status'] = sub.status
                data['subscription_start_date'] = sub.start_date.isoformat() if sub.start_date else None
                data['subscription_end_date'] = sub.end_date.isoformat() if sub.end_date else None
                # effective_status via serializer logic inline
                now = timezone.now()
                if not sub.start_date or not sub.end_date:
                    effective = 'pending'
                elif sub.start_date > now:
                    effective = 'pending'
                elif sub.status == 'active':
                    effective = 'expired' if sub.end_date <= now else 'active'
                elif sub.status == 'cancelled':
                    effective = 'expired' if sub.end_date <= now else 'cancelled_active'
                else:
                    effective = sub.status
                data['subscription_effective_status'] = effective
        except Exception:
            pass

        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='promo/validate')
    def validate_promo(self, request):
        """Validate input promo code without incrementing used_count"""
        serializer = PromoCodeValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        promo = serializer.validated_data['promo']
        
        promo_serializer = PromoCodeSerializer(promo, context={'request': request})
        return Response(promo_serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='subscription/mock-activate')
    def mock_activate(self, request):
        """Mock activation of a paid/any subscription plan for dev/testing"""
        billing_demo_enabled = getattr(settings, 'BILLING_DEMO_ENABLED', False)
        if not billing_demo_enabled:
            return Response(
                {"detail": "Mock activation is disabled in this environment."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        plan_id = request.data.get('plan_id')
        if not plan_id:
            return Response({"detail": "plan_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            plan = Plan.objects.get(id=plan_id, is_active=True)
        except Plan.DoesNotExist:
            return Response({"detail": "Active plan not found"}, status=status.HTTP_404_NOT_FOUND)
            
        if plan.code == 'free':
            return Response(
                {"detail": "Free plan cannot be mock activated as a paid transaction."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        provider_profile = request.user.provider_profile
        
        with transaction.atomic():
            subscription = services.create_subscription(provider_profile, plan)
            services.activate_paid_subscription(subscription)
        
        result_serializer = SubscriptionSerializer(subscription, context={'request': request})
        data = result_serializer.data
        data['is_demo'] = True
        data['provider'] = 'mock'
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='subscription/cancel')
    def cancel_subscription(self, request):
        """Cancel active subscription renewal at period end"""
        provider_profile = request.user.provider_profile
        
        with transaction.atomic():
            sub = Subscription.objects.select_for_update().filter(
                provider_profile=provider_profile,
                status='active'
            ).first()
            
            if sub:
                sub.status = 'cancelled'
                sub.cancelled_at = timezone.now()
                sub.save(update_fields=['status', 'cancelled_at'])
                
        return self._get_subscription_response(request)


class SubscriptionQuoteView(APIView):
    """Non-mutating preview of subscription checkout pricing including promo discounts."""
    permission_classes = [permissions.IsAuthenticated, IsProviderAuthenticated, IsNotBlockedProvider]

    def post(self, request):
        from decimal import Decimal, ROUND_HALF_UP
        from apps.billing.models import PromoCode

        plan_code = request.data.get('plan_code', '')
        promo_code_str = request.data.get('promo_code', '')

        if not plan_code:
            return Response({"detail": "plan_code is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            plan = Plan.objects.get(code=plan_code, is_active=True)
        except Plan.DoesNotExist:
            return Response({"detail": "Active plan not found."}, status=status.HTTP_404_NOT_FOUND)

        if plan.code == 'free':
            return Response({"detail": "Free plan has no payment quote."}, status=status.HTTP_400_BAD_REQUEST)

        # Normalize promo
        promo_code = None
        promo_valid = False
        promo_message = ''
        if promo_code_str:
            promo_code_str = promo_code_str.strip().upper()
            try:
                promo_code = PromoCode.objects.get(code=promo_code_str)
                # Check eligibility
                now = timezone.now()
                eligible = True
                if promo_code.eligible_plans.exists():
                    eligible = promo_code.eligible_plans.filter(id=plan.id).exists()

                if (promo_code.is_active
                        and eligible
                        and (not promo_code.starts_at or promo_code.starts_at <= now)
                        and (not promo_code.expires_at or promo_code.expires_at > now)
                        and promo_code.used_count < promo_code.max_uses):
                    promo_valid = True
                else:
                    promo_message = 'Promo code is not applicable.'
                    promo_code = None  # Don't apply invalid promo
            except PromoCode.DoesNotExist:
                promo_message = 'Promo code not found.'

        # Calculate prices
        prices = services.calculate_subscription_price(plan, promo_code)

        active_provider = getattr(settings, 'BILLING_PAYMENT_PROVIDER', 'mock').lower()

        # Provider amount calculation
        provider_amount = prices['final_amount']
        provider_currency = prices['currency']
        conversion_rate = Decimal('1.00')
        conversion_source = 'direct'

        if active_provider == 'paypal':
            conversion_enabled = getattr(settings, 'PAYPAL_SANDBOX_CONVERSION_ENABLED', True)
            if conversion_enabled:
                rate = getattr(settings, 'PAYPAL_SANDBOX_KZT_PER_USD', Decimal('450.00'))
                if isinstance(rate, (int, float)):
                    rate = Decimal(str(rate))
                if rate > 0:
                    provider_amount = (prices['final_amount'] / rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    provider_currency = getattr(settings, 'PAYPAL_SANDBOX_CURRENCY', 'USD')
                    conversion_rate = rate
                    conversion_source = 'paypal_sandbox_fixed'

        # Generate a simple fingerprint of this quote
        import hashlib, json as _json
        fingerprint_data = {
            'plan_code': plan_code,
            'promo_code': promo_code_str or None,
            'final_amount': str(prices['final_amount']),
            'provider_amount': str(provider_amount),
            'provider_currency': provider_currency,
        }
        quote_fingerprint = hashlib.sha256(
            _json.dumps(fingerprint_data, sort_keys=True).encode()
        ).hexdigest()[:16]

        return Response({
            'plan_code': plan.code,
            'plan_name_ru': plan.name_ru,
            'plan_name_en': plan.name_en,
            'plan_name_kz': plan.name_kz,
            'duration_days': plan.duration_days,
            'original_amount': str(prices['original_amount']),
            'discount_amount': str(prices['discount_amount']),
            'final_amount': str(prices['final_amount']),
            'original_currency': prices['currency'],
            'provider_amount': str(provider_amount),
            'provider_currency': provider_currency,
            'conversion_rate': str(conversion_rate),
            'conversion_source': conversion_source,
            'promo_code': promo_code_str or None,
            'promo_valid': promo_valid,
            'promo_message': promo_message if not promo_valid and promo_code_str else '',
            'active_provider': active_provider,
            'quote_fingerprint': quote_fingerprint,
        })


import logging as _logging
_webhook_logger = _logging.getLogger(__name__ + '.webhook')


class BillingWebhookView(APIView):
    """
    POST /api/v1/billing/webhook/{provider}/

    Receives and processes billing provider webhook events.

    Authentication: HMAC signature only (X-Billing-Signature header).
    No JWT required. AllowAny is required so the view is reachable by the provider.
    Business mutations are delegated entirely to process_billing_webhook().

    Response codes:
      200 {"status": "processed"}         — new event processed
      200 {"status": "already_processed"} — duplicate; idempotent
      200 {"status": "ignored"}           — stale/irrelevant event
      202 {"status": "processing"}        — another worker handling
      401                                 — missing/invalid signature
      400                                 — invalid payload structure
      500                                 — internal error (provider should retry)
    """
    permission_classes = [permissions.AllowAny]
    http_method_names = ['post']

    def post(self, request, provider=None):
        # 1. Validate provider against billing registry (not BILLING_PAYMENT_PROVIDER)
        provider_name = (provider or '').lower()
        if provider_name not in BILLING_ADAPTER_REGISTRY:
            return Response(
                {"detail": "Unknown billing provider"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Instantiate adapter
        try:
            adapter = get_subscription_payment_adapter(provider_name)
        except Exception:
            _webhook_logger.exception("Failed to instantiate adapter for provider=%s", provider_name)
            return Response({"detail": "Internal error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 3. Read raw body exactly once
        raw_body = request.body
        if not raw_body:
            return Response({"detail": "Empty body"}, status=status.HTTP_400_BAD_REQUEST)

        # 4. Verify HMAC signature — no business logic before this point
        try:
            sig_ok = adapter.verify_webhook(raw_body, request.META)
        except Exception:
            _webhook_logger.exception(
                "verify_webhook raised for provider=%s", provider_name
            )
            return Response({"detail": "Internal error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not sig_ok:
            # Never reveal expected signature or details
            return Response(
                {"detail": "Invalid signature"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 5. Delegate all business mutations to the processing service
        try:
            result = process_billing_webhook(
                provider_name=provider_name,
                adapter=adapter,
                raw_body=raw_body,
            )
        except Exception:
            _webhook_logger.exception(
                "process_billing_webhook unhandled exception provider=%s", provider_name
            )
            return Response({"detail": "Internal error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        result_status = result.get('status', 'failed')
        error_code = result.get('error_code', '')

        # 6. Map result to HTTP response
        if result_status == 'failed':
            # Map parse/payload errors to 400; others to 500 for retry
            if error_code in ('parse_error', 'normalize_error'):
                return Response({"detail": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST)
            # Internal/processing errors → 500 so provider retries
            return Response({"detail": "Internal error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if result_status == 'processing':
            return Response({"status": "processing"}, status=status.HTTP_202_ACCEPTED)

        # processed / already_processed / ignored
        return Response({"status": result_status}, status=status.HTTP_200_OK)


from django.shortcuts import redirect
from decimal import Decimal
from apps.billing.services.webhooks import _handle_payment_confirmed, _send_payment_confirmed_notification
from apps.payments.providers.paypal.client import get_paypal_billing_client

class PayPalSubscriptionReturnView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        token = request.query_params.get("token")
        payment_id = request.query_params.get("payment_id")
        locale = request.query_params.get("locale", "ru")
        if locale not in ('ru', 'en', 'kz'):
            locale = 'ru'
        
        base_url = getattr(settings, 'BILLING_RETURN_URL', 'http://localhost:3000/{locale}/provider/billing')
        redirect_url = base_url.replace('{locale}', locale)
        connector = '&' if '?' in redirect_url else '?'
        
        if token and payment_id:
            redirect_url = f"{redirect_url}{connector}payment_id={payment_id}&token={token}&status=success"
        else:
            redirect_url = f"{redirect_url}{connector}status=cancel"
            
        return redirect(redirect_url)


class PayPalSubscriptionCaptureView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsProviderAuthenticated, IsNotBlockedProvider]

    def post(self, request):
        paypal_order_id = request.data.get("paypal_order_id")
        if not paypal_order_id:
            return Response({"detail": "paypal_order_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Locate payment safely by paypal_order_id and provider='paypal'
        try:
            payment = Payment.objects.select_related('subscription', 'provider_profile').get(
                provider_payment_id=paypal_order_id,
                provider='paypal'
            )
        except Payment.DoesNotExist:
            return Response({"detail": "Payment transaction not found."}, status=status.HTTP_404_NOT_FOUND)

        # 2. Check ownership
        if payment.provider_profile != request.user.provider_profile:
            return Response({"detail": "You do not own this transaction."}, status=status.HTTP_403_FORBIDDEN)

        # 3. Idempotent success check
        if payment.status == Payment.Status.PAID:
            return Response({"status": "success", "payment_status": "paid"})

        client = get_paypal_billing_client()

        # 4. Fetch order details from PayPal to verify identity, amount, currency, custom_id
        try:
            order_data = client.get_order(paypal_order_id)
        except Exception as e:
            return Response({"detail": f"Failed to retrieve PayPal order: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate custom_id prefix and value
        purchase_units = order_data.get("purchase_units", [])
        if not purchase_units:
            return Response({"detail": "PayPal order has no purchase units."}, status=status.HTTP_400_BAD_REQUEST)

        custom_id = purchase_units[0].get("custom_id", "")
        if custom_id != f"billing-payment-{payment.id}":
            return Response({"detail": "PayPal order custom ID mismatch."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate amount & currency
        paypal_amount = purchase_units[0].get("amount", {}).get("value")
        paypal_currency = purchase_units[0].get("amount", {}).get("currency_code")

        if Decimal(str(paypal_amount)) != payment.provider_amount:
            return Response({"detail": "Payment amount mismatch."}, status=status.HTTP_400_BAD_REQUEST)
        if paypal_currency != payment.provider_currency:
            return Response({"detail": "Payment currency mismatch."}, status=status.HTTP_400_BAD_REQUEST)

        # 5. Capture order if APPROVED
        paypal_status = order_data.get("status")
        capture_id = ""
        capture_status = ""

        if paypal_status == "APPROVED":
            try:
                cap_resp = client.capture_order(paypal_order_id, f"paypal-billing-capture-{payment.id}")
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
            # Already captured
            p_units_resp = order_data.get("purchase_units", [])
            if p_units_resp:
                captures = p_units_resp[0].get("payments", {}).get("captures", [])
                if captures:
                    capture_id = captures[0].get("id", "")
                    capture_status = captures[0].get("status", "")

        # Only a confirmed COMPLETED capture may enter success
        if paypal_status == "COMPLETED" or capture_status == "COMPLETED":
            payment.raw_response = {
                "paypal_order_id": paypal_order_id,
                "paypal_capture_id": capture_id,
                "order_status": paypal_status,
                "capture_status": capture_status or "COMPLETED",
                "custom_id": custom_id,
                "sandbox": (getattr(settings, 'PAYPAL_MODE', 'sandbox') == 'sandbox')
            }
            payment.save(update_fields=['raw_response'])

            # Route to central confirmation logic
            normalized = {
                "occurred_at": timezone.now().isoformat()
            }
            dispatch_result = _handle_payment_confirmed(payment, normalized)

            if dispatch_result == 'processed':
                transaction.on_commit(lambda: _send_payment_confirmed_notification(payment.id))

            return Response({"status": "success", "payment_status": "paid"})
        else:
            return Response({"detail": f"PayPal order status is {paypal_status}. Only COMPLETED capture is allowed."}, status=status.HTTP_400_BAD_REQUEST)
