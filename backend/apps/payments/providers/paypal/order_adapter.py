import logging
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.utils import timezone
from apps.payments.models import PaymentTransaction
from apps.payments.adapters import BasePaymentAdapter
from apps.payments.providers.paypal.client import get_paypal_orders_client

logger = logging.getLogger(__name__)

class PayPalOrderPaymentAdapter(BasePaymentAdapter):
    def create_checkout(self, transaction: PaymentTransaction) -> str:
        # 1. Lock conversion rate and store snapshot details
        conversion_enabled = getattr(settings, 'PAYPAL_SANDBOX_CONVERSION_ENABLED', True)
        if conversion_enabled:
            if getattr(settings, 'PAYPAL_MODE', 'sandbox') != 'sandbox':
                raise ValueError("Fixed sandbox currency conversion is only allowed when PAYPAL_MODE=sandbox.")
            
            rate = getattr(settings, 'PAYPAL_SANDBOX_KZT_PER_USD', Decimal("450.00"))
            if rate <= 0:
                raise ValueError("Conversion rate must be positive.")
                
            provider_currency = getattr(settings, 'PAYPAL_SANDBOX_CURRENCY', 'USD')
            provider_amount = (transaction.amount / rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            if provider_amount <= Decimal("0.00"):
                raise ValueError("Converted provider amount rounds to 0.00. Purchase amount is too low.")
        else:
            provider_currency = transaction.currency
            provider_amount = transaction.amount
            rate = Decimal("1.00")

        # Mutate the PaymentTransaction record to persist the conversion snapshot
        transaction.provider_amount = provider_amount
        transaction.provider_currency = provider_currency
        transaction.conversion_rate = rate
        transaction.conversion_source = 'paypal_sandbox_fixed' if conversion_enabled else 'direct'
        transaction.conversion_locked_at = timezone.now()
        transaction.provider = 'paypal'
        transaction.save(update_fields=[
            'provider_amount', 'provider_currency', 'conversion_rate',
            'conversion_source', 'conversion_locked_at', 'provider'
        ])

        # 2. Build return & cancel redirect URLs pointing to the frontend
        base_return_url = settings.PAYMENT_RETURN_URL.replace("{order_id}", str(transaction.order_id))
        connector = '&' if '?' in base_return_url else '?'
        return_url = f"{base_return_url}{connector}transaction_id={transaction.id}&status=success"

        base_cancel_url = settings.PAYMENT_CANCEL_URL.replace("{order_id}", str(transaction.order_id))
        cancel_url = f"{base_cancel_url}{connector}transaction_id={transaction.id}&status=cancel"

        # 3. Create PayPal Order payload
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {
                    "currency_code": str(provider_currency),
                    "value": str(provider_amount)
                },
                "custom_id": f"marketplace-payment-{transaction.id}",
                "description": f"Marketplace Order #{transaction.order_id}"
            }],
            "application_context": {
                "return_url": return_url,
                "cancel_url": cancel_url,
                "user_action": "PAY_NOW"
            }
        }

        # Send stable creating Request ID
        request_id = f"paypal-order-create-{transaction.id}"
        
        client = get_paypal_orders_client()
        try:
            resp = client.create_order(payload, request_id)
        except Exception as e:
            logger.error(f"Failed to create PayPal order checkout for transaction={transaction.id}: {str(e)}")
            raise

        order_id = resp.get("id")
        if not order_id:
            raise RuntimeError("PayPal order creation response did not return an order ID")

        # Find approval link
        approve_url = ""
        for link in resp.get("links", []):
            if link.get("rel") == "approve":
                approve_url = link.get("href")
                break

        if not approve_url:
            raise RuntimeError("PayPal order creation response did not contain an approve link")

        # Setup whitelisted raw_response
        raw_response = {
            "paypal_order_id": order_id,
            "paypal_capture_id": "",
            "order_status": resp.get("status"),
            "capture_status": "",
            "custom_id": f"marketplace-payment-{transaction.id}",
            "sandbox": (getattr(settings, 'PAYPAL_MODE', 'sandbox') == 'sandbox')
        }

        transaction.provider_payment_id = order_id
        transaction.provider_reference = order_id
        transaction.raw_response = raw_response
        transaction.save(update_fields=['provider_payment_id', 'provider_reference', 'raw_response'])

        return approve_url

    def verify_webhook(self, request) -> bool:
        client = get_paypal_orders_client()
        webhook_id = getattr(settings, 'PAYPAL_ORDERS_WEBHOOK_ID', '')
        if not webhook_id:
            logger.warning("PAYPAL_ORDERS_WEBHOOK_ID is not configured; rejecting webhook")
            return False

        try:
            # Django request body read
            try:
                body = request._request.body
            except AttributeError:
                body = getattr(request, 'body', b'')
            
            import json
            payload = json.loads(body.decode('utf-8'))
        except Exception:
            return False

        return client.verify_webhook(request.META, payload, webhook_id)

    def parse_webhook_payload(self, payload: dict) -> dict:
        event_type = payload.get('event_type')
        resource = payload.get('resource', {})
        
        custom_id = resource.get('custom_id') or ''
        if not custom_id.startswith('marketplace-payment-'):
            raise ValueError(f"Invalid custom_id prefix for marketplace webhook: {custom_id}")

        # Map status
        if event_type == 'PAYMENT.CAPTURE.COMPLETED':
            status = 'success'
        elif event_type == 'PAYMENT.CAPTURE.DENIED':
            status = 'failed'
        elif event_type == 'PAYMENT.CAPTURE.PENDING':
            status = 'pending'
        else:
            status = 'success'

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
        capture_id = resource.get('id', '')

        raw_response = {
            "paypal_order_id": order_id,
            "paypal_capture_id": capture_id,
            "order_status": resource.get('status', ''),
            "capture_status": resource.get('status', ''),
            "custom_id": custom_id,
            "sandbox": (getattr(settings, 'PAYPAL_MODE', 'sandbox') == 'sandbox')
        }

        # Extract transaction ID from custom_id e.g. "marketplace-payment-{id}"
        tx_id = custom_id.split('marketplace-payment-')[1]

        return {
            "status": status,
            "transaction_id": tx_id,
            "provider_reference": order_id,
            "amount": amount,
            "currency": currency,
            "provider_payment_id": order_id,
            "raw_response": raw_response
        }
