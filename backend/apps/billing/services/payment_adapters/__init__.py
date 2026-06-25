import hashlib
import hmac
import json
import uuid
import logging
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class BaseSubscriptionPaymentAdapter:
    """
    Base interface for billing subscription payment adapters.
    Adapters are responsible for:
      - Creating checkout sessions (create_checkout)
      - Verifying incoming webhook authenticity (verify_webhook)
      - Parsing raw webhook bytes into a normalized dict (parse_webhook_payload)
      - Normalizing parsed payload into a canonical event dict (normalize_webhook_event)

    Adapters must NOT:
      - Update Payment rows
      - Activate Subscriptions
      - Redeem Promo codes
      - Create notifications
    """

    def create_checkout(self, payment, locale=None):
        raise NotImplementedError("create_checkout must be implemented by subclasses")

    def verify_configuration(self):
        raise NotImplementedError("verify_configuration must be implemented by subclasses")

    def verify_webhook(self, raw_body: bytes, headers) -> bool:
        """
        Verify the authenticity of an incoming webhook request.
        raw_body: exact bytes from request.body
        headers: dict-like object of request headers
        Returns True if authentic, False otherwise.
        Must never log the secret, received signature, or expected signature.
        """
        raise NotImplementedError("verify_webhook must be implemented by subclasses")

    def parse_webhook_payload(self, raw_body: bytes, headers) -> dict:
        """
        Parse the raw webhook body bytes into a dict.
        Raises ValueError on invalid JSON or structural errors.
        Must not perform business mutations.
        """
        raise NotImplementedError("parse_webhook_payload must be implemented by subclasses")

    def normalize_webhook_event(self, parsed_payload: dict) -> dict:
        """
        Normalize a parsed payload dict into a canonical event dict:
        {
            "event_id": str,          # unique event ID, or "" if absent
            "event_type": str,        # "payment_confirmed" | "payment_failed" | "payment_cancelled" | other
            "provider_payment_id": str,
            "provider_reference": str,
            "payment_status": str,
            "amount": str,            # Decimal-string representation e.g. "8910.00"
            "currency": str,          # e.g. "KZT"
            "occurred_at": str,       # ISO 8601 or ""
            "safe_metadata": dict     # allow-listed non-sensitive fields only
        }
        Never include signature, secret, card data, tokens, or full provider metadata.
        """
        raise NotImplementedError("normalize_webhook_event must be implemented by subclasses")


import threading


class MockSubscriptionPaymentAdapter(BaseSubscriptionPaymentAdapter):
    """
    Mock adapter for dev/test environments.
    Implements real HMAC-SHA256 signature verification using BILLING_PAYMENT_WEBHOOK_SECRET.
    The mock provider is a security test provider, not an authentication bypass.
    Signature header: X-Billing-Signature: sha256=<hex_digest>
    """
    _call_count = 0
    _lock = threading.Lock()

    @classmethod
    def reset_call_count(cls):
        with cls._lock:
            cls._call_count = 0

    @classmethod
    def get_call_count(cls):
        with cls._lock:
            return cls._call_count

    def create_checkout(self, payment, locale=None):
        with self._lock:
            self.__class__._call_count += 1

        # Whitelist and fallback locale
        if locale not in ('ru', 'en', 'kz'):
            locale = 'ru'

        provider_payment_id = f"mock-sub-{uuid.uuid4()}"
        provider_reference = f"billing-payment-{payment.id}"

        # Build return URL safely replacing locale
        base_return_url = getattr(
            settings,
            'BILLING_RETURN_URL',
            'http://localhost:3000/{locale}/provider/billing'
        )
        return_url = base_return_url.replace('{locale}', locale)

        # Append parameters
        connector = '&' if '?' in return_url else '?'
        checkout_url = f"{return_url}{connector}billing_status=return&payment_id={payment.id}"

        # Safe sanitized raw response (no secrets/tokens/signed URLs)
        raw_response = {
            "provider_payment_id": provider_payment_id,
            "provider_reference": provider_reference,
            "checkout_created": True,
            "is_demo": True
        }

        return {
            "provider_payment_id": provider_payment_id,
            "provider_reference": provider_reference,
            "checkout_url": checkout_url,
            "checkout_expires_at": timezone.now() + timedelta(minutes=30),
            "raw_response": raw_response
        }

    def verify_configuration(self):
        # Always verified for mock provider
        pass

    def verify_webhook(self, raw_body: bytes, headers) -> bool:
        """
        Verify HMAC-SHA256 signature.
        Expected header: X-Billing-Signature: sha256=<hex_digest>
        Computes HMAC over the exact raw_body bytes.
        Never logs secret, received signature, or expected signature.
        """
        secret = getattr(settings, 'BILLING_PAYMENT_WEBHOOK_SECRET', '') or ''
        if not secret:
            # No secret configured: reject all webhooks (fail secure)
            logger.warning("BILLING_PAYMENT_WEBHOOK_SECRET is not configured; rejecting webhook")
            return False

        # Support both django request.META style and plain dict
        sig_header = (
            headers.get('X-Billing-Signature')
            or headers.get('HTTP_X_BILLING_SIGNATURE')
            or ''
        )

        if not sig_header:
            return False

        # Expected format: "sha256=<hex_digest>"
        if not sig_header.startswith('sha256='):
            return False

        received_hex = sig_header[len('sha256='):]
        if not received_hex:
            return False

        if not raw_body:
            return False

        # Compute expected HMAC
        try:
            mac = hmac.new(
                secret.encode('utf-8'),
                raw_body,
                hashlib.sha256
            )
            expected_hex = mac.hexdigest()
        except Exception:
            return False

        # Constant-time comparison — never log either value
        return hmac.compare_digest(expected_hex, received_hex)

    def parse_webhook_payload(self, raw_body: bytes, headers) -> dict:
        """
        Parse JSON from raw_body bytes.
        Raises ValueError on invalid JSON or empty body.
        """
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
        """
        Normalize mock adapter payload into canonical event dict.
        Expected mock payload fields:
          event_id, event_type, provider_payment_id, provider_reference,
          payment_status, amount, currency, occurred_at
        """
        event_id = str(parsed_payload.get('event_id', '') or '')
        event_type = str(parsed_payload.get('event_type', '') or '')
        provider_payment_id = str(parsed_payload.get('provider_payment_id', '') or '')
        provider_reference = str(parsed_payload.get('provider_reference', '') or '')
        payment_status = str(parsed_payload.get('payment_status', '') or '')
        amount_raw = parsed_payload.get('amount', '')
        currency = str(parsed_payload.get('currency', 'KZT') or 'KZT').upper()
        occurred_at = str(parsed_payload.get('occurred_at', '') or '')

        # Normalize amount to string representation
        if amount_raw is not None and amount_raw != '':
            amount_str = str(amount_raw)
        else:
            amount_str = ''

        # Safe metadata: only allow-listed, non-sensitive fields
        safe_metadata = {}
        for key in ('is_demo', 'event_id', 'event_type'):
            if key in parsed_payload:
                safe_metadata[key] = parsed_payload[key]

        return {
            "event_id": event_id,
            "event_type": event_type,
            "provider_payment_id": provider_payment_id,
            "provider_reference": provider_reference,
            "payment_status": payment_status,
            "amount": amount_str,
            "currency": currency,
            "occurred_at": occurred_at,
            "safe_metadata": safe_metadata,
        }


# ---------------------------------------------------------------------------
# Billing adapter registry
# ---------------------------------------------------------------------------
# Maps billing provider names to their adapter classes.
# This registry is completely separate from the marketplace payment adapter
# registry in apps.payments.adapters. Marketplace adapters must never appear
# here, and BILLING_PAYMENT_PROVIDER / PAYMENT_PROVIDER remain independent.

from .paypal import PayPalSubscriptionPaymentAdapter

BILLING_ADAPTER_REGISTRY: dict[str, type] = {
    'mock': MockSubscriptionPaymentAdapter,
    'paypal': PayPalSubscriptionPaymentAdapter,
}


def get_subscription_payment_adapter(provider=None) -> BaseSubscriptionPaymentAdapter:
    """
    Return the billing subscription payment adapter for the given provider name.
    Falls back to settings.BILLING_PAYMENT_PROVIDER when provider is None.
    Raises ImproperlyConfigured for unknown providers.
    The provider name must be registered in BILLING_ADAPTER_REGISTRY.
    """
    if provider is None:
        provider = getattr(settings, 'BILLING_PAYMENT_PROVIDER', 'mock')

    provider = (provider or '').lower()
    adapter_class = BILLING_ADAPTER_REGISTRY.get(provider)
    if adapter_class is None:
        raise ImproperlyConfigured(
            f"Unknown billing payment provider '{provider}'. "
            f"Registered providers: {list(BILLING_ADAPTER_REGISTRY.keys())}"
        )
    return adapter_class()
