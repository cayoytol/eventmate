import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.utils import timezone
from apps.payments.providers.paypal.client import get_paypal_billing_client
from apps.payments.url_helpers import extract_paypal_approval_url
from apps.billing.services.payment_adapters import BaseSubscriptionPaymentAdapter

logger = logging.getLogger(__name__)

class PayPalSubscriptionPaymentAdapter(BaseSubscriptionPaymentAdapter):
    def verify_configuration(self):
        # Configuration is verified via system checks.
        pass

    def create_checkout(self, payment, locale=None):
        # 1. Lock conversion rate and store snapshot details
        conversion_enabled = getattr(settings, 'PAYPAL_SANDBOX_CONVERSION_ENABLED', True)
        if conversion_enabled:
            if getattr(settings, 'PAYPAL_MODE', 'sandbox') != 'sandbox':
                raise ValueError("Fixed sandbox currency conversion is only allowed when PAYPAL_MODE=sandbox.")
            
            rate = getattr(settings, 'PAYPAL_SANDBOX_KZT_PER_USD', Decimal("450.00"))
            if rate <= 0:
                raise ValueError("Conversion rate must be positive.")
                
            provider_currency = getattr(settings, 'PAYPAL_SANDBOX_CURRENCY', 'USD')
            provider_amount = (payment.amount / rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            if provider_amount <= Decimal("0.00"):
                raise ValueError("Converted provider amount rounds to 0.00. Purchase amount is too low.")
        else:
            provider_currency = payment.currency
            provider_amount = payment.amount
            rate = Decimal("1.00")

        # Mutate the Payment record to persist the conversion snapshot
        payment.provider_amount = provider_amount
        payment.provider_currency = provider_currency
        payment.conversion_rate = rate
        payment.conversion_source = 'paypal_sandbox_fixed' if conversion_enabled else 'direct'
        payment.conversion_locked_at = timezone.now()
        payment.provider = 'paypal'
        payment.save(update_fields=[
            'provider_amount', 'provider_currency', 'conversion_rate',
            'conversion_source', 'conversion_locked_at', 'provider'
        ])

        # 2. Build return & cancel redirect URLs pointing to the frontend
        if locale not in ('ru', 'en', 'kz'):
            locale = 'ru'
            
        # Return URL points to the dedicated billing checkout page
        base_return_url = getattr(
            settings,
            'BILLING_CHECKOUT_RETURN_URL',
            getattr(settings, 'BILLING_RETURN_URL',
                    'http://localhost:3000/{locale}/provider/billing/checkout')
        )
        # Ensure return goes to checkout page
        return_url_base = base_return_url.replace('{locale}', locale)
        if '/billing/checkout' not in return_url_base:
            return_url_base = return_url_base.rstrip('/') + '/checkout'
        connector = '&' if '?' in return_url_base else '?'
        plan_code = payment.plan_code_snapshot or ''
        return_url = f"{return_url_base}{connector}payment_id={payment.id}&plan={plan_code}"

        base_cancel_url = getattr(
            settings,
            'BILLING_CHECKOUT_CANCEL_URL',
            getattr(settings, 'BILLING_CANCEL_URL',
                    'http://localhost:3000/{locale}/provider/billing')
        )
        cancel_url_base = base_cancel_url.replace('{locale}', locale)
        cancel_connector = '&' if '?' in cancel_url_base else '?'
        cancel_url = f"{cancel_url_base}{cancel_connector}status=cancel"

        # 3. Create PayPal Order payload
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {
                    "currency_code": str(provider_currency),
                    "value": str(provider_amount)
                },
                "custom_id": f"billing-payment-{payment.id}",
                "description": f"Subscription: {payment.plan_name_en_snapshot or payment.plan_code_snapshot}"
            }],
            "application_context": {
                "return_url": return_url,
                "cancel_url": cancel_url,
                "user_action": "PAY_NOW"
            }
        }

        # Send stable creating Request ID
        request_id = f"paypal-billing-create-{payment.id}"
        
        client = get_paypal_billing_client()
        try:
            resp = client.create_order(payload, request_id)
        except Exception as e:
            logger.error(f"Failed to create PayPal subscription checkout for payment={payment.id}: {str(e)}")
            raise

        order_id = resp.get("id")
        if not order_id:
            raise RuntimeError("PayPal order creation response did not return an order ID")

        # Find approval link (accepts 'approve' or 'payer-action' rels)
        try:
            approve_url = extract_paypal_approval_url(resp.get("links", []))
        except ValueError as e:
            raise RuntimeError(f"PayPal order creation response did not contain a valid approval link: {e}")

        # Setup whitelisted raw_response
        raw_response = {
            "paypal_order_id": order_id,
            "paypal_capture_id": "",
            "order_status": resp.get("status"),
            "capture_status": "",
            "custom_id": f"billing-payment-{payment.id}",
            "sandbox": (getattr(settings, 'PAYPAL_MODE', 'sandbox') == 'sandbox')
        }

        return {
            "provider_payment_id": order_id,
            "provider_reference": order_id,
            "checkout_url": approve_url,
            "checkout_expires_at": timezone.now() + timedelta(minutes=30),
            "raw_response": raw_response
        }

    def verify_webhook(self, raw_body: bytes, headers) -> bool:
        client = get_paypal_billing_client()
        webhook_id = getattr(settings, 'PAYPAL_BILLING_WEBHOOK_ID', '')
        if not webhook_id:
            logger.warning("PAYPAL_BILLING_WEBHOOK_ID is not configured; rejecting webhook")
            return False
            
        try:
            payload = self.parse_webhook_payload(raw_body, headers)
        except Exception:
            return False
            
        return client.verify_webhook(headers, payload, webhook_id)

    def parse_webhook_payload(self, raw_body: bytes, headers) -> dict:
        import json
        if not raw_body:
            raise ValueError("Empty webhook body")
        try:
            payload = json.loads(raw_body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"Invalid JSON in webhook body: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Webhook body must be a JSON object")
        return payload

    def normalize_webhook_event(self, parsed_payload: dict) -> dict:
        event_type = parsed_payload.get('event_type')
        resource = parsed_payload.get('resource', {})
        
        custom_id = resource.get('custom_id') or ''
        if not custom_id.startswith('billing-payment-'):
            raise ValueError(f"Invalid custom_id prefix for billing webhook: {custom_id}")
            
        # Map event type
        if event_type == 'PAYMENT.CAPTURE.COMPLETED':
            mapped_event = 'payment_confirmed'
        elif event_type == 'PAYMENT.CAPTURE.DENIED':
            mapped_event = 'payment_failed'
        elif event_type == 'CHECKOUT.ORDER.APPROVED':
            mapped_event = 'payment_pending'
        elif event_type == 'PAYMENT.CAPTURE.PENDING':
            mapped_event = 'payment_pending'
        else:
            mapped_event = 'other'

        # Extract order ID
        order_id = resource.get('supplementary_data', {}).get('related_ids', {}).get('order_id', '')
        if not order_id:
            for link in resource.get('links', []):
                href = link.get('href', '')
                if 'checkout/orders/' in href:
                    parts = href.split('checkout/orders/')
                    if len(parts) > 1:
                        order_id = parts[1].split('/')[0]
                        break

        amount = resource.get('amount', {}).get('value', '')
        currency = resource.get('amount', {}).get('currency_code', '')

        safe_metadata = {
            "paypal_order_id": order_id,
            "paypal_capture_id": resource.get('id', ''),
            "order_status": resource.get('status', ''),
            "capture_status": resource.get('status', ''),
            "custom_id": custom_id,
            "sandbox": (getattr(settings, 'PAYPAL_MODE', 'sandbox') == 'sandbox')
        }

        return {
            "event_id": parsed_payload.get('id', ''),
            "event_type": mapped_event,
            "provider_payment_id": order_id,
            "provider_reference": resource.get('id', ''),
            "payment_status": resource.get('status', ''),
            "amount": amount,
            "currency": currency,
            "occurred_at": parsed_payload.get('create_time', ''),
            "safe_metadata": safe_metadata
        }
