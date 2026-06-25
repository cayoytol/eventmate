"""
Management command: paypal_sandbox_check

Safe diagnostic for PayPal Sandbox configuration.
Does NOT print secrets, tokens, or full approval URLs.
Does NOT create real PaymentTransaction database records.

Usage:
    python manage.py paypal_sandbox_check --domain marketplace
    python manage.py paypal_sandbox_check --domain billing
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Safe PayPal Sandbox diagnostic check. Does not create DB records or log secrets.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            choices=['marketplace', 'billing'],
            required=True,
            help='Which PayPal domain to check: marketplace or billing'
        )

    def handle(self, *args, **options):
        domain = options['domain']
        self.stdout.write(f"domain={domain}")

        if domain == 'marketplace':
            self._check_domain(
                domain=domain,
                client_id_setting='PAYPAL_ORDERS_CLIENT_ID',
                client_secret_setting='PAYPAL_ORDERS_CLIENT_SECRET',
                dummy_ids=['dummy_orders_client_id', 'dummy_orders_client_secret'],
                get_client_fn=self._get_orders_client,
            )
        else:
            self._check_domain(
                domain=domain,
                client_id_setting='PAYPAL_BILLING_CLIENT_ID',
                client_secret_setting='PAYPAL_BILLING_CLIENT_SECRET',
                dummy_ids=['dummy_billing_client_id', 'dummy_billing_client_secret'],
                get_client_fn=self._get_billing_client,
            )

    def _get_orders_client(self):
        from apps.payments.providers.paypal.client import get_paypal_orders_client
        return get_paypal_orders_client()

    def _get_billing_client(self):
        from apps.payments.providers.paypal.client import get_paypal_billing_client
        return get_paypal_billing_client()

    def _check_domain(self, domain, client_id_setting, client_secret_setting, dummy_ids, get_client_fn):
        mode = getattr(settings, 'PAYPAL_MODE', 'sandbox')
        provider = getattr(settings, 'PAYMENT_PROVIDER' if domain == 'marketplace' else 'BILLING_PAYMENT_PROVIDER', 'mock')
        self.stdout.write(f"provider={provider}")
        self.stdout.write(f"mode={mode}")

        # Check credentials configured
        client_id = getattr(settings, client_id_setting, '')
        client_secret = getattr(settings, client_secret_setting, '')

        client_id_configured = bool(client_id) and client_id.lower() not in dummy_ids
        client_secret_configured = bool(client_secret) and client_secret.lower() not in dummy_ids

        self.stdout.write(f"client_id_configured={str(client_id_configured).lower()}")
        self.stdout.write(f"client_secret_configured={str(client_secret_configured).lower()}")

        if not client_id_configured or not client_secret_configured:
            self.stdout.write("oauth_success=false")
            self.stdout.write("order_created=false")
            self.stdout.write("approval_url_present=false")
            self.stderr.write(
                self.style.ERROR(
                    f"BLOCKED: Real {client_id_setting} and {client_secret_setting} must be set before H1 verification."
                )
            )
            return

        # Try OAuth
        try:
            client = get_client_fn()
            token = client.get_access_token()
            oauth_success = bool(token)
        except Exception as e:
            self.stdout.write("oauth_success=false")
            self.stdout.write("order_created=false")
            self.stdout.write("approval_url_present=false")
            # Do NOT log the error message as it may contain credentials
            self.stderr.write(self.style.ERROR("OAuth failed. Check credentials and network connectivity."))
            return

        self.stdout.write(f"oauth_success={str(oauth_success).lower()}")

        if not oauth_success:
            self.stdout.write("order_created=false")
            self.stdout.write("approval_url_present=false")
            return

        # Create a minimal test order
        from decimal import Decimal, ROUND_HALF_UP
        try:
            payload = {
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {
                        "currency_code": "USD",
                        "value": "0.01"  # Minimum sandbox amount
                    },
                    "custom_id": f"{domain}-diagnostic-check",
                    "description": f"EventMate {domain} diagnostic - NOT a real transaction"
                }],
                "application_context": {
                    "return_url": "https://example.com/return",
                    "cancel_url": "https://example.com/cancel",
                    "user_action": "PAY_NOW"
                }
            }
            resp = client.create_order(payload, f"diagnostic-{domain}-check-001")
            order_created = bool(resp.get('id'))
        except Exception:
            self.stdout.write("order_created=false")
            self.stdout.write("approval_url_present=false")
            self.stderr.write(self.style.ERROR("Order creation failed. Check credentials and PayPal app permissions."))
            return

        self.stdout.write(f"order_created={str(order_created).lower()}")

        if not order_created:
            self.stdout.write("approval_url_present=false")
            return

        # Extract approval URL
        from apps.payments.url_helpers import extract_paypal_approval_url
        try:
            approval_url = extract_paypal_approval_url(resp.get('links', []))
            approval_url_present = True
            # Parse hostname safely
            import urllib.parse
            parsed = urllib.parse.urlparse(approval_url)
            approval_hostname = parsed.hostname or 'unknown'
        except ValueError:
            approval_url_present = False
            approval_hostname = 'none'

        self.stdout.write(f"approval_url_present={str(approval_url_present).lower()}")
        if approval_url_present:
            self.stdout.write(f"approval_hostname={approval_hostname}")
            self.stdout.write(self.style.SUCCESS(f"H1 {domain.upper()} diagnostic: PASS"))
        else:
            self.stdout.write("approval_hostname=none")
            self.stderr.write(self.style.ERROR(f"H1 {domain.upper()} diagnostic: FAIL - No valid approval URL found"))
