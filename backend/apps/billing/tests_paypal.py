import json
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import ProviderProfile
from apps.billing.models import Plan, Subscription
from apps.payments.models import Payment
from apps.billing.checks import check_paypal_configuration
from apps.billing.services.payment_adapters.paypal import PayPalSubscriptionPaymentAdapter

User = get_user_model()


class PayPalConfigurationCheckTests(TestCase):
    @patch('sys.argv', ['manage.py', 'check'])
    @override_settings(
        BILLING_PAYMENT_PROVIDER='paypal',
        PAYMENT_PROVIDER='paypal',
        PAYPAL_BILLING_CLIENT_ID='',
        PAYPAL_BILLING_CLIENT_SECRET='',
        PAYPAL_BILLING_WEBHOOK_ID='',
        PAYPAL_ORDERS_CLIENT_ID='',
        PAYPAL_ORDERS_CLIENT_SECRET='',
        PAYPAL_ORDERS_WEBHOOK_ID='',
        PAYPAL_MODE='sandbox',
        PAYPAL_API_BASE_URL='https://api-m.sandbox.paypal.com',
        PAYPAL_SANDBOX_CONVERSION_ENABLED=True,
        PAYPAL_SANDBOX_KZT_PER_USD=Decimal("450.00"),
        PAYPAL_SANDBOX_CURRENCY='USD'
    )
    def test_missing_credentials_fails(self):
        errors = check_paypal_configuration(None)
        self.assertEqual(len(errors), 6)
        error_ids = {e.id for e in errors}
        self.assertEqual(error_ids, {
            "PAYPAL.E001", "PAYPAL.E002", "PAYPAL.E003",
            "PAYPAL.E004", "PAYPAL.E005", "PAYPAL.E006"
        })

    @patch('sys.argv', ['manage.py', 'check'])
    @override_settings(
        BILLING_PAYMENT_PROVIDER='paypal',
        PAYMENT_PROVIDER='paypal',
        PAYPAL_BILLING_CLIENT_ID='id1',
        PAYPAL_BILLING_CLIENT_SECRET='sec1',
        PAYPAL_BILLING_WEBHOOK_ID='wh1',
        PAYPAL_ORDERS_CLIENT_ID='id2',
        PAYPAL_ORDERS_CLIENT_SECRET='sec2',
        PAYPAL_ORDERS_WEBHOOK_ID='wh2',
        PAYPAL_MODE='sandbox',
        PAYPAL_API_BASE_URL='https://api-m.paypal.com',  # Live URL in sandbox mode!
        PAYPAL_SANDBOX_CONVERSION_ENABLED=True,
        PAYPAL_SANDBOX_KZT_PER_USD=Decimal("450.00"),
        PAYPAL_SANDBOX_CURRENCY='USD'
    )
    def test_sandbox_url_mismatch(self):
        errors = check_paypal_configuration(None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "PAYPAL.E007")

    @patch('sys.argv', ['manage.py', 'check'])
    @override_settings(
        BILLING_PAYMENT_PROVIDER='mock',
        PAYMENT_PROVIDER='mock',
        PAYPAL_MODE='live',  # Live mode
        PAYPAL_SANDBOX_CONVERSION_ENABLED=True,  # enabled!
        PAYPAL_SANDBOX_KZT_PER_USD=Decimal("450.00"),
        PAYPAL_SANDBOX_CURRENCY='USD'
    )
    def test_conversion_enabled_outside_sandbox(self):
        errors = check_paypal_configuration(None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "PAYPAL.E008")

    @patch('sys.argv', ['manage.py', 'check'])
    @override_settings(
        BILLING_PAYMENT_PROVIDER='mock',
        PAYMENT_PROVIDER='mock',
        PAYPAL_MODE='sandbox',
        PAYPAL_API_BASE_URL='https://api-m.sandbox.paypal.com',
        PAYPAL_SANDBOX_CONVERSION_ENABLED=True,
        PAYPAL_SANDBOX_KZT_PER_USD=Decimal("-450.00"),  # negative
        PAYPAL_SANDBOX_CURRENCY='USD'
    )
    def test_negative_conversion_rate(self):
        errors = check_paypal_configuration(None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "PAYPAL.E009")

    @patch('sys.argv', ['manage.py', 'check'])
    @override_settings(
        BILLING_PAYMENT_PROVIDER='mock',
        PAYMENT_PROVIDER='mock',
        PAYPAL_MODE='sandbox',
        PAYPAL_API_BASE_URL='https://api-m.sandbox.paypal.com',
        PAYPAL_SANDBOX_CONVERSION_ENABLED=True,
        PAYPAL_SANDBOX_KZT_PER_USD=Decimal("450.00"),
        PAYPAL_SANDBOX_CURRENCY='INVALID_CURRENCY'  # invalid
    )
    def test_invalid_conversion_currency(self):
        errors = check_paypal_configuration(None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "PAYPAL.E010")


class PayPalSubscriptionPaymentAdapterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test_provider@test.com", password="password123", role="provider"
        )
        self.provider_profile, _ = ProviderProfile.objects.get_or_create(user=self.user, defaults={"bio": "Test bio"})
        self.plan = Plan.objects.create(
            code="pro",
            name_ru="Платный",
            price=5000,
            duration_days=30,
            is_active=True
        )
        self.subscription = Subscription.objects.create(
            provider_profile=self.provider_profile,
            plan=self.plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            status='pending'
        )
        self.payment = Payment.objects.create(
            provider_profile=self.provider_profile,
            subscription=self.subscription,
            amount=self.plan.price,
            currency="KZT",
            status=Payment.Status.PENDING,
            plan_code_snapshot="pro"
        )
        self.adapter = PayPalSubscriptionPaymentAdapter()

    @override_settings(
        PAYPAL_MODE='sandbox',
        PAYPAL_SANDBOX_CONVERSION_ENABLED=True,
        PAYPAL_SANDBOX_KZT_PER_USD=Decimal("450.00"),
        PAYPAL_SANDBOX_CURRENCY='USD'
    )
    @patch('apps.billing.services.payment_adapters.paypal.get_paypal_billing_client')
    def test_create_checkout_conversion(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.create_order.return_value = {
            "id": "PAYPAL_ORDER_123",
            "status": "CREATED",
            "links": [{"rel": "approve", "href": "https://sandbox.paypal.com/approve/123"}]
        }
        mock_get_client.return_value = mock_client

        result = self.adapter.create_checkout(self.payment, locale="ru")

        # Check conversion values
        self.payment.refresh_from_db()
        # 5000 / 450 = 11.11111 -> quantize(0.01) -> 11.11
        self.assertEqual(self.payment.provider_amount, Decimal("11.11"))
        self.assertEqual(self.payment.provider_currency, "USD")
        self.assertEqual(self.payment.conversion_rate, Decimal("450.00"))
        self.assertEqual(self.payment.conversion_source, "paypal_sandbox_fixed")
        self.assertIsNotNone(self.payment.conversion_locked_at)
        self.assertEqual(self.payment.provider, "paypal")

        self.assertEqual(result["provider_payment_id"], "PAYPAL_ORDER_123")
        self.assertEqual(result["checkout_url"], "https://sandbox.paypal.com/approve/123")
        self.assertIn("paypal_order_id", result["raw_response"])

    @override_settings(
        PAYPAL_MODE='live',  # Live mode
        PAYPAL_SANDBOX_CONVERSION_ENABLED=True,
        PAYPAL_SANDBOX_KZT_PER_USD=Decimal("450.00")
    )
    def test_create_checkout_rejects_conversion_outside_sandbox(self):
        with self.assertRaises(ValueError) as ctx:
            self.adapter.create_checkout(self.payment)
        self.assertIn("only allowed when PAYPAL_MODE=sandbox", str(ctx.exception))

    @override_settings(
        PAYPAL_MODE='sandbox',
        PAYPAL_SANDBOX_CONVERSION_ENABLED=True,
        PAYPAL_SANDBOX_KZT_PER_USD=Decimal("450.00")
    )
    def test_create_checkout_rejects_zero_converted_amount(self):
        low_payment = Payment.objects.create(
            provider_profile=self.provider_profile,
            subscription=self.subscription,
            amount=Decimal("0.01"),  # 0.01 KZT
            currency="KZT",
            status=Payment.Status.PENDING,
            plan_code_snapshot="pro"
        )
        with self.assertRaises(ValueError) as ctx:
            self.adapter.create_checkout(low_payment)
        self.assertIn("rounds to 0.00", str(ctx.exception))


class PayPalSubscriptionCaptureViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test_provider@test.com", password="password123", role="provider"
        )
        self.provider_profile, _ = ProviderProfile.objects.get_or_create(user=self.user, defaults={"bio": "Test bio"})
        
        self.other_user = User.objects.create_user(
            email="other_provider@test.com", password="password123", role="provider"
        )
        self.other_profile, _ = ProviderProfile.objects.get_or_create(user=self.other_user, defaults={"bio": "Other bio"})

        self.plan = Plan.objects.create(
            code="pro",
            name_ru="Платный",
            price=4500,
            duration_days=30,
            is_active=True
        )
        self.subscription = Subscription.objects.create(
            provider_profile=self.provider_profile,
            plan=self.plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            status='pending'
        )
        self.payment = Payment.objects.create(
            provider_profile=self.provider_profile,
            subscription=self.subscription,
            amount=self.plan.price,
            currency="KZT",
            provider="paypal",
            provider_payment_id="PAYPAL_ORDER_123",
            provider_amount=Decimal("10.00"),
            provider_currency="USD",
            status=Payment.Status.PENDING,
            plan_duration_days_snapshot=30,
            plan_code_snapshot="pro"
        )
        self.capture_url = "/api/v1/billing/paypal/capture/"

    def test_anonymous_rejected(self):
        response = self.client.post(self.capture_url, {"paypal_order_id": "PAYPAL_ORDER_123"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_owner_rejected(self):
        self.client.force_authenticate(user=self.other_user)
        response = self.client.post(self.capture_url, {"paypal_order_id": "PAYPAL_ORDER_123"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('apps.billing.views.get_paypal_billing_client')
    def test_idempotent_already_paid(self, mock_get_client):
        self.payment.status = Payment.Status.PAID
        self.payment.save()
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.capture_url, {"paypal_order_id": "PAYPAL_ORDER_123"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")

    @patch('apps.billing.views.get_paypal_billing_client')
    def test_capture_success_workflow(self, mock_get_client):
        mock_client = MagicMock()
        # Mock get_order returning APPROVED status
        mock_client.get_order.return_value = {
            "id": "PAYPAL_ORDER_123",
            "status": "APPROVED",
            "purchase_units": [{
                "custom_id": f"billing-payment-{self.payment.id}",
                "amount": {
                    "value": "10.00",
                    "currency_code": "USD"
                }
            }]
        }
        # Mock capture_order returning COMPLETED status
        mock_client.capture_order.return_value = {
            "id": "PAYPAL_ORDER_123",
            "status": "COMPLETED",
            "purchase_units": [{
                "payments": {
                    "captures": [{
                        "id": "CAPTURE_ID_123",
                        "status": "COMPLETED"
                    }]
                }
            }]
        }
        mock_get_client.return_value = mock_client

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.capture_url, {"paypal_order_id": "PAYPAL_ORDER_123"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")

        # Verify payment status is PAID
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PAID)
        self.assertEqual(self.payment.raw_response["paypal_capture_id"], "CAPTURE_ID_123")
        self.assertEqual(self.payment.raw_response["order_status"], "COMPLETED")

        # Verify subscription is activated
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, "active")

    @patch('apps.billing.views.get_paypal_billing_client')
    def test_capture_fails_on_custom_id_mismatch(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_order.return_value = {
            "id": "PAYPAL_ORDER_123",
            "status": "APPROVED",
            "purchase_units": [{
                "custom_id": "billing-payment-9999",  # incorrect ID
                "amount": {
                    "value": "10.00",
                    "currency_code": "USD"
                }
            }]
        }
        mock_get_client.return_value = mock_client

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.capture_url, {"paypal_order_id": "PAYPAL_ORDER_123"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("custom ID mismatch", response.data["detail"])


class PayPalWebhookTests(APITestCase):
    def setUp(self):
        self.webhook_url = "/api/v1/billing/webhook/paypal/"

    @override_settings(PAYPAL_BILLING_WEBHOOK_ID='wh1')
    @patch('apps.billing.services.payment_adapters.paypal.get_paypal_billing_client')
    def test_webhook_signature_failure_rejected(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.verify_webhook.return_value = False
        mock_get_client.return_value = mock_client

        payload = {
            "id": "EV-123",
            "event_type": "CHECKOUT.ORDER.APPROVED",
            "resource": {
                "id": "PAYPAL_ORDER_123",
                "status": "APPROVED",
                "custom_id": "billing-payment-1"
            }
        }
        response = self.client.post(
            self.webhook_url,
            payload,
            format='json',
            HTTP_PAYPAL_TRANSMISSION_SIG='dummy'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ActiveProviderAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test_provider@test.com", password="password123", role="provider"
        )
        self.provider_profile, _ = ProviderProfile.objects.get_or_create(user=self.user, defaults={"bio": "Test bio"})

    @override_settings(BILLING_PAYMENT_PROVIDER='paypal')
    def test_current_subscription_reports_paypal(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/billing/subscription/current/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["active_provider"], "paypal")

    @override_settings(BILLING_PAYMENT_PROVIDER='mock')
    def test_current_subscription_reports_mock(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/billing/subscription/current/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["active_provider"], "mock")
