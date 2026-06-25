"""
Management command: send_mock_billing_webhook

Sends a signed mock billing webhook to the local development endpoint.

Usage:
    python manage.py send_mock_billing_webhook --payment-id <id> --status paid
    python manage.py send_mock_billing_webhook --payment-id <id> --status failed
    python manage.py send_mock_billing_webhook --payment-id <id> --status cancelled

Requirements:
    BILLING_PAYMENT_PROVIDER=mock
    BILLING_DEMO_ENABLED=True
    BILLING_PAYMENT_WEBHOOK_SECRET must be set (non-empty)

Security:
    - Never prints the webhook secret
    - Clearly labels operation as demo
    - Signs body with HMAC-SHA256 before sending
    - Does NOT create an unsigned bypass endpoint
"""
import hashlib
import hmac
import json
import uuid
import urllib.request
import urllib.error
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Send a signed mock billing webhook to the local endpoint. "
        "Demo use only. Requires BILLING_DEMO_ENABLED=True and BILLING_PAYMENT_PROVIDER=mock."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--payment-id',
            type=int,
            required=True,
            help='ID of the billing Payment to target'
        )
        parser.add_argument(
            '--status',
            type=str,
            required=True,
            choices=['paid', 'failed', 'cancelled'],
            help='Payment outcome to simulate: paid | failed | cancelled'
        )
        parser.add_argument(
            '--endpoint',
            type=str,
            default='http://localhost:8000/api/v1/billing/webhook/mock/',
            help='Webhook endpoint URL (default: local dev server)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print request summary without sending (never prints the secret)'
        )

    def handle(self, *args, **options):
        # Guard: demo only
        billing_demo_enabled = getattr(settings, 'BILLING_DEMO_ENABLED', False)
        if not billing_demo_enabled:
            raise CommandError(
                "BILLING_DEMO_ENABLED is not True. "
                "This command is for demo/development use only."
            )

        provider = getattr(settings, 'BILLING_PAYMENT_PROVIDER', 'mock')
        if provider != 'mock':
            raise CommandError(
                f"BILLING_PAYMENT_PROVIDER is '{provider}', expected 'mock'. "
                "This command only works with the mock adapter."
            )

        secret = getattr(settings, 'BILLING_PAYMENT_WEBHOOK_SECRET', '') or ''
        if not secret:
            raise CommandError(
                "BILLING_PAYMENT_WEBHOOK_SECRET is not set. "
                "Set it to a non-empty string in your .env before using this command."
            )

        payment_id = options['payment_id']
        target_status = options['status']
        endpoint = options['endpoint']
        dry_run = options['dry_run']

        # Resolve event_type from status
        status_to_event = {
            'paid': 'payment_confirmed',
            'failed': 'payment_failed',
            'cancelled': 'payment_cancelled',
        }
        event_type = status_to_event[target_status]
        status_to_payment_status = {
            'paid': 'paid',
            'failed': 'failed',
            'cancelled': 'cancelled',
        }
        payment_status = status_to_payment_status[target_status]

        # Fetch payment to build realistic payload
        from apps.payments.models import Payment
        try:
            payment = Payment.objects.select_related('provider_profile').get(id=payment_id)
        except Payment.DoesNotExist:
            raise CommandError(f"Payment with id={payment_id} does not exist.")

        if payment.provider != 'mock':
            raise CommandError(
                f"Payment {payment_id} has provider='{payment.provider}', expected 'mock'."
            )

        event_id = f"demo-event-{uuid.uuid4()}"
        occurred_at = timezone.now().isoformat()

        payload = {
            "event_id": event_id,
            "event_type": event_type,
            "provider_payment_id": payment.provider_payment_id or f"mock-sub-{payment_id}",
            "provider_reference": payment.provider_reference or f"billing-payment-{payment_id}",
            "payment_status": payment_status,
            "amount": str(payment.amount),
            "currency": payment.currency,
            "occurred_at": occurred_at,
            "is_demo": True,
        }

        # Serialize to exact bytes
        raw_body = json.dumps(payload, separators=(',', ':')).encode('utf-8')

        # Compute HMAC-SHA256
        mac = hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256)
        sig_hex = mac.hexdigest()
        sig_header = f"sha256={sig_hex}"

        self.stdout.write(self.style.WARNING(
            "\n[DEMO] send_mock_billing_webhook — this is a development demo operation"
        ))
        self.stdout.write(f"  Payment ID : {payment_id}")
        self.stdout.write(f"  Provider   : mock")
        self.stdout.write(f"  Event type : {event_type}")
        self.stdout.write(f"  Amount     : {payment.amount} {payment.currency}")
        self.stdout.write(f"  Event ID   : {event_id}")
        self.stdout.write(f"  Endpoint   : {endpoint}")
        self.stdout.write(f"  Signature  : sha256=<hidden>")
        # Never print the actual secret or full sig_header value

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                "[DEMO] Dry run — request not sent. Body preview (first 200 chars):"
            ))
            preview = raw_body.decode('utf-8')[:200]
            self.stdout.write(f"  {preview}")
            return

        # Send request
        req = urllib.request.Request(
            url=endpoint,
            data=raw_body,
            method='POST',
            headers={
                'Content-Type': 'application/json',
                'X-Billing-Signature': sig_header,
                'X-Demo': 'true',
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                response_body = resp.read().decode('utf-8')
                http_status = resp.status
        except urllib.error.HTTPError as exc:
            response_body = exc.read().decode('utf-8') if exc.fp else ''
            http_status = exc.code
        except urllib.error.URLError as exc:
            raise CommandError(
                f"Could not connect to {endpoint}: {exc.reason}. "
                "Is the dev server running?"
            )

        self.stdout.write(f"  HTTP Status: {http_status}")
        self.stdout.write(f"  Response   : {response_body[:200]}")

        if http_status == 200:
            self.stdout.write(self.style.SUCCESS("[DEMO] Webhook delivered successfully."))
        elif http_status == 401:
            self.stdout.write(self.style.ERROR(
                "[DEMO] Signature rejected (401). "
                "Check that BILLING_PAYMENT_WEBHOOK_SECRET matches on both ends."
            ))
        else:
            self.stdout.write(self.style.WARNING(f"[DEMO] Unexpected HTTP {http_status}."))
