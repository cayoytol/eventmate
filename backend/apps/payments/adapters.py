from abc import ABC, abstractmethod
from django.conf import settings
from .models import PaymentTransaction

class BasePaymentAdapter(ABC):
    """Abstract base class for all payment provider adapters"""
    
    @abstractmethod
    def create_checkout(self, transaction: PaymentTransaction) -> str:
        """
        Generate checkout URL for client redirection.
        Should return checkout_url string.
        """
        pass
        
    @abstractmethod
    def verify_webhook(self, request) -> bool:
        """Verify the cryptographic signature of the webhook request"""
        pass
        
    @abstractmethod
    def parse_webhook_payload(self, payload: dict) -> dict:
        """Parse webhook payload into a normalized dictionary format"""
        pass


import hmac
import hashlib

class MockPaymentAdapter(BasePaymentAdapter):
    """Simulated payment adapter for development and testing"""
    
    def create_checkout(self, transaction: PaymentTransaction) -> str:
        # Interpolate order_id safely
        return settings.PAYMENT_RETURN_URL.replace("{order_id}", str(transaction.order_id)) + f"?status=success&transaction_id={transaction.id}"
        
    def verify_webhook(self, request) -> bool:
        """
        Verify signature for mock testing framework.
        Signature is HMAC-SHA256 of raw request body using PAYMENT_WEBHOOK_SECRET.
        """
        secret = getattr(settings, 'PAYMENT_WEBHOOK_SECRET', '')
        if not secret:
            if settings.DEBUG:
                return True
            return False
            
        signature = request.headers.get('X-Payment-Signature', '')
        if not signature:
            signature = request.META.get('HTTP_X_PAYMENT_SIGNATURE', '')
        if not signature:
            return False
            
        try:
            # Use raw django request body to avoid DRF cached body read issues
            body = request._request.body
        except AttributeError:
            body = getattr(request, 'body', b'')
            
        expected = hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)
        
    def parse_webhook_payload(self, payload: dict) -> dict:
        status_val = payload.get("status", "success")
        tx_id = payload.get("transaction_id")
        ref = payload.get("provider_reference", "mock-ref")
        amount = payload.get("amount")
        currency = payload.get("currency", "KZT")
        
        # sanitize raw response to exclude headers, signatures, card details, or secrets
        raw_response = {
            "status": status_val,
            "provider_reference": ref,
            "amount": amount,
            "currency": currency,
        }
        if tx_id:
            raw_response["transaction_id"] = tx_id
            
        return {
            "status": status_val,
            "transaction_id": tx_id,
            "provider_reference": ref,
            "amount": amount,
            "currency": currency,
            "provider_payment_id": payload.get("provider_payment_id", f"mock-payment-{ref}"),
            "raw_response": raw_response
        }


import base64
import json
import urllib.request
import urllib.error

class CloudPaymentsAdapter(BasePaymentAdapter):
    """Production payment adapter for CloudPayments integration"""

    def create_checkout(self, transaction: PaymentTransaction) -> str:
        url = f"{settings.PAYMENT_API_URL.rstrip('/')}/orders/create"
        
        # Format redirect URLs
        success_url = settings.PAYMENT_RETURN_URL.replace("{order_id}", str(transaction.order_id))
        fail_url = settings.PAYMENT_CANCEL_URL.replace("{order_id}", str(transaction.order_id))
        
        payload = {
            "Amount": float(transaction.amount),
            "Currency": transaction.currency,
            "Description": f"Payment for order #{transaction.order_id}",
            "InvoiceId": str(transaction.order_id),
            "AccountId": str(transaction.order.client_id),
            "SuccessRedirectUrl": success_url,
            "FailRedirectUrl": fail_url,
            "SendEmail": False,
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST"
        )
        
        # Basic Auth authentication using Public ID and API Secret
        auth_str = f"{settings.PAYMENT_PUBLIC_KEY}:{settings.PAYMENT_SECRET_KEY}"
        auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
        req.add_header("Authorization", f"Basic {auth_b64}")
        
        try:
            with urllib.request.urlopen(req, timeout=settings.PAYMENT_TIMEOUT_SECONDS) as response:
                resp_data = json.loads(response.read().decode('utf-8'))
                if not resp_data.get("Success"):
                    raise ValueError(resp_data.get("Message", "CloudPayments order creation failed"))
                
                model = resp_data.get("Model", {})
                checkout_url = model.get("Url")
                if not checkout_url:
                    raise ValueError("CloudPayments response did not contain checkout URL")
                
                # Save provider reference
                model_id = model.get("Id")
                if model_id is not None:
                    transaction.provider_payment_id = str(model_id)
                    transaction.provider_reference = str(model_id)
                    
                model_num = model.get("Number")
                if model_num:
                    transaction.raw_response = {"Number": model_num}
                    
                transaction.save()
                return checkout_url
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"CloudPayments API call failed with status {e.code}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"CloudPayments network error: {e.reason}")
        except Exception as e:
            raise RuntimeError(f"CloudPayments API call failed: {str(e)}")

    def verify_webhook(self, request) -> bool:
        signature = request.headers.get('Content-HMAC')
        if not signature:
            signature = request.headers.get('X-Content-HMAC')
        if not signature:
            signature = request.META.get('HTTP_CONTENT_HMAC')
        if not signature:
            signature = request.META.get('HTTP_X_CONTENT_HMAC')
            
        if not signature:
            return False

        secret = getattr(settings, 'PAYMENT_WEBHOOK_SECRET', '')
        if not secret:
            secret = getattr(settings, 'PAYMENT_SECRET_KEY', '')
        if not secret:
            return False

        try:
            body = request._request.body
        except AttributeError:
            body = getattr(request, 'body', b'')

        expected = base64.b64encode(
            hmac.new(secret.encode('utf-8'), body, hashlib.sha256).digest()
        ).decode('utf-8')

        return hmac.compare_digest(expected, signature)

    def parse_webhook_payload(self, payload: dict) -> dict:
        invoice_id = payload.get("InvoiceId")
        ref = str(payload.get("TransactionId", ""))
        amount = payload.get("Amount")
        currency = payload.get("Currency", "KZT")
        status_raw = payload.get("Status", "Completed")
        date_time = payload.get("DateTime")
        reason_code = payload.get("ReasonCode")

        # Safe response sanitization
        raw_response = {
            "TransactionId": ref,
            "InvoiceId": invoice_id,
            "Amount": amount,
            "Currency": currency,
            "Status": status_raw,
        }
        if date_time:
            raw_response["DateTime"] = date_time
        if reason_code:
            raw_response["ReasonCode"] = reason_code

        # Map raw status to our internal enum
        status_map = {
            "Completed": "success",
            "Authorized": "pending",
            "Failed": "failed",
            "Cancelled": "cancelled"
        }
        internal_status = status_map.get(status_raw, "success")

        return {
            "status": internal_status,
            "transaction_id": None,
            "invoice_id": invoice_id,
            "provider_reference": ref,
            "amount": amount,
            "currency": currency,
            "provider_payment_id": ref,
            "raw_response": raw_response
        }


def get_payment_adapter() -> BasePaymentAdapter:
    """Helper to instantiate the active payment provider adapter"""
    provider = getattr(settings, "PAYMENT_PROVIDER", "mock").lower()
    if provider == "mock":
        return MockPaymentAdapter()
    elif provider == "cloudpayments":
        return CloudPaymentsAdapter()
    elif provider == "paypal":
        client_id = getattr(settings, 'PAYPAL_ORDERS_CLIENT_ID', '')
        client_secret = getattr(settings, 'PAYPAL_ORDERS_CLIENT_SECRET', '')
        if not client_id or not client_secret:
            from apps.payments.exceptions import PaymentProviderConfigurationError
            raise PaymentProviderConfigurationError("PayPal Sandbox marketplace payment is not configured.")
        from .providers.paypal.order_adapter import PayPalOrderPaymentAdapter
        return PayPalOrderPaymentAdapter()
    else:
        raise ValueError(f"Unsupported payment provider: {provider}")
