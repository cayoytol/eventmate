import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import ProviderProfile
from apps.catalog.models import Category, Service
from apps.marketplace.models import EventRequest, Offer, Order
from apps.payments.models import PaymentTransaction
from apps.payments.providers.paypal.order_adapter import PayPalOrderPaymentAdapter

User = get_user_model()


class PayPalOrderPaymentAdapterTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            email='client@test.com', password='password123', role='client'
        )
        self.provider_user = User.objects.create_user(
            email='provider@test.com', password='password123', role='provider'
        )
        self.provider_profile = ProviderProfile.objects.create(user=self.provider_user)
        self.category = Category.objects.create(name_ru='Декор', slug='decor')
        self.service = Service.objects.create(
            provider=self.provider_profile,
            category=self.category,
            title='Wedding Decoration',
            price_amount=120000,
            price_type='event',
            city='Алматы'
        )
        self.request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            title='My Wedding Decor',
            city='Алматы',
            event_date=timezone.now(),
            budget_min=100000,
            budget_max=150000,
            status=EventRequest.Status.OFFERS
        )
        self.offer = Offer.objects.create(
            request=self.request,
            service=self.service,
            provider_profile=self.provider_profile,
            price=135000,
            status=Offer.Status.SENT
        )
        self.order = Order.objects.create(
            offer=self.offer,
            client=self.client_user,
            provider_profile=self.provider_profile,
            status=Order.Status.CONFIRMED,
            payment_status=Order.PaymentStatus.UNPAID,
            price_agreed=135000,
            service_snapshot={}
        )
        self.transaction = PaymentTransaction.objects.create(
            order=self.order,
            provider="paypal",
            amount=self.order.price_agreed,
            currency="KZT",
            status=PaymentTransaction.Status.PENDING,
            idempotency_key=str(uuid.uuid4())
        )
        self.adapter = PayPalOrderPaymentAdapter()

    @override_settings(
        PAYPAL_MODE='sandbox',
        PAYPAL_SANDBOX_CONVERSION_ENABLED=True,
        PAYPAL_SANDBOX_KZT_PER_USD=Decimal("450.00"),
        PAYPAL_SANDBOX_CURRENCY='USD'
    )
    @patch('apps.payments.providers.paypal.order_adapter.get_paypal_orders_client')
    def test_create_checkout_conversion(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.create_order.return_value = {
            "id": "PAYPAL_ORDER_789",
            "status": "CREATED",
            "links": [{"rel": "approve", "href": "https://paypal.com/approve/789"}]
        }
        mock_get_client.return_value = mock_client

        approve_url = self.adapter.create_checkout(self.transaction)

        # Check conversion values
        self.transaction.refresh_from_db()
        # 135000 / 450 = 300.00
        self.assertEqual(self.transaction.provider_amount, Decimal("300.00"))
        self.assertEqual(self.transaction.provider_currency, "USD")
        self.assertEqual(self.transaction.conversion_rate, Decimal("450.00"))
        self.assertEqual(self.transaction.conversion_source, "paypal_sandbox_fixed")
        self.assertIsNotNone(self.transaction.conversion_locked_at)
        self.assertEqual(self.transaction.provider, "paypal")
        self.assertEqual(self.transaction.provider_payment_id, "PAYPAL_ORDER_789")
        self.assertEqual(approve_url, "https://paypal.com/approve/789")

    @override_settings(
        PAYPAL_MODE='live',
        PAYPAL_SANDBOX_CONVERSION_ENABLED=True,
        PAYPAL_SANDBOX_KZT_PER_USD=Decimal("450.00")
    )
    def test_create_checkout_rejects_conversion_outside_sandbox(self):
        with self.assertRaises(ValueError) as ctx:
            self.adapter.create_checkout(self.transaction)
        self.assertIn("only allowed when PAYPAL_MODE=sandbox", str(ctx.exception))


class PayPalOrderCaptureViewTests(APITestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            email='client@test.com', password='password123', role='client'
        )
        self.other_user = User.objects.create_user(
            email='other_client@test.com', password='password123', role='client'
        )
        self.provider_user = User.objects.create_user(
            email='provider@test.com', password='password123', role='provider'
        )
        self.provider_profile = ProviderProfile.objects.create(user=self.provider_user)
        self.category = Category.objects.create(name_ru='Декор', slug='decor')
        self.service = Service.objects.create(
            provider=self.provider_profile,
            category=self.category,
            title='Wedding Decoration',
            price_amount=120000,
            price_type='event',
            city='Алматы'
        )
        self.request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            title='My Wedding Decor',
            city='Алматы',
            event_date=timezone.now(),
            budget_min=100000,
            budget_max=150000,
            status=EventRequest.Status.OFFERS
        )
        self.offer = Offer.objects.create(
            request=self.request,
            service=self.service,
            provider_profile=self.provider_profile,
            price=135000,
            status=Offer.Status.SENT
        )
        self.order = Order.objects.create(
            offer=self.offer,
            client=self.client_user,
            provider_profile=self.provider_profile,
            status=Order.Status.CONFIRMED,
            payment_status=Order.PaymentStatus.UNPAID,
            price_agreed=135000,
            service_snapshot={}
        )
        self.transaction = PaymentTransaction.objects.create(
            order=self.order,
            provider="paypal",
            amount=self.order.price_agreed,
            currency="KZT",
            provider_payment_id="PAYPAL_ORDER_789",
            provider_amount=Decimal("300.00"),
            provider_currency="USD",
            status=PaymentTransaction.Status.PENDING,
            idempotency_key=str(uuid.uuid4())
        )
        self.capture_url = "/api/v1/payments/paypal/capture/"

    def test_anonymous_rejected(self):
        response = self.client.post(self.capture_url, {"paypal_order_id": "PAYPAL_ORDER_789"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_owner_rejected(self):
        self.client.force_authenticate(user=self.other_user)
        response = self.client.post(self.capture_url, {"paypal_order_id": "PAYPAL_ORDER_789"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('apps.payments.views.get_paypal_orders_client')
    def test_idempotent_already_paid(self, mock_get_client):
        self.transaction.status = PaymentTransaction.Status.SUCCESS
        self.transaction.save()
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post(self.capture_url, {"paypal_order_id": "PAYPAL_ORDER_789"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")

    @patch('apps.payments.views.get_paypal_orders_client')
    def test_capture_success_workflow(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_order.return_value = {
            "id": "PAYPAL_ORDER_789",
            "status": "APPROVED",
            "purchase_units": [{
                "custom_id": f"marketplace-payment-{self.transaction.id}",
                "amount": {
                    "value": "300.00",
                    "currency_code": "USD"
                }
            }]
        }
        mock_client.capture_order.return_value = {
            "id": "PAYPAL_ORDER_789",
            "status": "COMPLETED",
            "purchase_units": [{
                "payments": {
                    "captures": [{
                        "id": "CAPTURE_789",
                        "status": "COMPLETED"
                    }]
                }
            }]
        }
        mock_get_client.return_value = mock_client

        self.client.force_authenticate(user=self.client_user)
        response = self.client.post(self.capture_url, {"paypal_order_id": "PAYPAL_ORDER_789"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")

        # Verify transaction status is SUCCESS
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, PaymentTransaction.Status.SUCCESS)

        # Verify order payment status is PAID
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)


class ActiveProviderAPITests(APITestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            email='client@test.com', password='password123', role='client'
        )
        self.provider_user = User.objects.create_user(
            email='provider@test.com', password='password123', role='provider'
        )
        self.provider_profile = ProviderProfile.objects.create(user=self.provider_user)
        self.category = Category.objects.create(name_ru='Декор', slug='decor')
        self.service = Service.objects.create(
            provider=self.provider_profile,
            category=self.category,
            title='Wedding Decoration',
            price_amount=120000,
            price_type='event',
            city='Алматы'
        )
        self.request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            title='My Wedding Decor',
            city='Алматы',
            event_date=timezone.now(),
            budget_min=100000,
            budget_max=150000,
            status=EventRequest.Status.OFFERS
        )
        self.offer = Offer.objects.create(
            request=self.request,
            service=self.service,
            provider_profile=self.provider_profile,
            price=135000,
            status=Offer.Status.SENT
        )
        self.order = Order.objects.create(
            offer=self.offer,
            client=self.client_user,
            provider_profile=self.provider_profile,
            status=Order.Status.CONFIRMED,
            payment_status=Order.PaymentStatus.UNPAID,
            price_agreed=135000,
            service_snapshot={}
        )

    @override_settings(PAYMENT_PROVIDER='paypal')
    def test_payment_status_reports_paypal(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.get(f"/api/v1/payments/orders/{self.order.id}/status/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["active_provider"], "paypal")

    @override_settings(PAYMENT_PROVIDER='mock')
    def test_payment_status_reports_mock(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.get(f"/api/v1/payments/orders/{self.order.id}/status/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["active_provider"], "mock")


class PayPalMarketplaceAdditionalTests(APITestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            email='client@test.com', password='password123', role='client'
        )
        self.other_user = User.objects.create_user(
            email='other_client@test.com', password='password123', role='client'
        )
        self.provider_user = User.objects.create_user(
            email='provider@test.com', password='password123', role='provider'
        )
        self.provider_profile = ProviderProfile.objects.create(user=self.provider_user)
        self.category = Category.objects.create(name_ru='Декор', slug='decor')
        self.service = Service.objects.create(
            provider=self.provider_profile,
            category=self.category,
            title='Wedding Decoration',
            price_amount=120000,
            price_type='event',
            city='Алматы'
        )
        self.request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            title='My Wedding Decor',
            city='Алматы',
            event_date=timezone.now(),
            budget_min=100000,
            budget_max=150000,
            status=EventRequest.Status.OFFERS
        )
        self.offer = Offer.objects.create(
            request=self.request,
            service=self.service,
            provider_profile=self.provider_profile,
            price=135000,
            status=Offer.Status.SENT
        )
        self.order = Order.objects.create(
            offer=self.offer,
            client=self.client_user,
            provider_profile=self.provider_profile,
            status=Order.Status.CONFIRMED,
            payment_status=Order.PaymentStatus.UNPAID,
            price_agreed=135000,
            service_snapshot={}
        )

    @override_settings(
        PAYMENT_PROVIDER='paypal',
        PAYPAL_MODE='sandbox',
        PAYPAL_ORDERS_CLIENT_ID='dummy_id',
        PAYPAL_ORDERS_CLIENT_SECRET='dummy_secret'
    )
    @patch('apps.payments.services.MarketplaceCheckoutService.perform_provider_operation')
    def test_existing_ready_checkout_returns_without_paypal_call(self, mock_perform):
        token = uuid.uuid4()
        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider="paypal",
            amount=self.order.price_agreed,
            currency="KZT",
            provider_payment_id="PAYPAL_ORDER_789",
            checkout_url="https://www.sandbox.paypal.com/checkoutnow?token=789",
            checkout_state=PaymentTransaction.CheckoutState.READY,
            checkout_initialization_token=token,
            idempotency_key=str(uuid.uuid4())
        )
        from apps.payments.services import MarketplaceCheckoutService
        tx_res, is_initializing, retry_after, action = MarketplaceCheckoutService.get_or_create_checkout(self.order.id, self.client_user)
        self.assertEqual(tx_res.id, tx.id)
        self.assertEqual(action, "ready")
        self.assertEqual(is_initializing, False)
        mock_perform.assert_not_called()

    @override_settings(
        PAYMENT_PROVIDER='paypal',
        PAYPAL_MODE='sandbox',
        PAYPAL_ORDERS_CLIENT_ID='dummy_id',
        PAYPAL_ORDERS_CLIENT_SECRET='dummy_secret'
    )
    def test_fresh_initializing_returns_202(self):
        token = uuid.uuid4()
        PaymentTransaction.objects.create(
            order=self.order,
            provider="paypal",
            amount=self.order.price_agreed,
            currency="KZT",
            checkout_state=PaymentTransaction.CheckoutState.INITIALIZING,
            checkout_initialization_started_at=timezone.now(),
            checkout_initialization_token=token,
            idempotency_key=str(uuid.uuid4())
        )
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post(f"/api/v1/payments/orders/{self.order.id}/create/")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["code"], "checkout_initializing")

    @override_settings(
        PAYMENT_PROVIDER='paypal',
        PAYPAL_MODE='sandbox',
        PAYPAL_CHECKOUT_INITIALIZATION_TIMEOUT_SECONDS=5,
        PAYPAL_ORDERS_CLIENT_ID='dummy_id',
        PAYPAL_ORDERS_CLIENT_SECRET='dummy_secret'
    )
    @patch('apps.payments.services.MarketplaceCheckoutService.perform_provider_operation')
    def test_stale_initializing_is_reclaimed(self, mock_perform):
        token = uuid.uuid4()
        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider="paypal",
            amount=self.order.price_agreed,
            currency="KZT",
            checkout_state=PaymentTransaction.CheckoutState.INITIALIZING,
            checkout_initialization_started_at=timezone.now() - timezone.timedelta(seconds=10),
            checkout_initialization_token=token,
            idempotency_key=str(uuid.uuid4())
        )
        mock_perform.return_value = {
            "checkout_url": "https://www.sandbox.paypal.com/checkoutnow?token=789",
            "provider_payment_id": "PAYPAL_ORDER_789",
            "raw_response": {"status": "CREATED"}
        }
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post(f"/api/v1/payments/orders/{self.order.id}/create/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tx.refresh_from_db()
        self.assertEqual(tx.checkout_state, PaymentTransaction.CheckoutState.READY)
        self.assertNotEqual(tx.checkout_initialization_token, token)

    @override_settings(
        PAYMENT_PROVIDER='paypal',
        PAYPAL_MODE='sandbox',
        PAYPAL_ORDERS_CLIENT_ID='dummy_id',
        PAYPAL_ORDERS_CLIENT_SECRET='dummy_secret'
    )
    def test_stale_worker_result_cannot_overwrite_new_attempt(self):
        token1 = uuid.uuid4()
        token2 = uuid.uuid4()
        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider="paypal",
            amount=self.order.price_agreed,
            currency="KZT",
            checkout_state=PaymentTransaction.CheckoutState.INITIALIZING,
            checkout_initialization_started_at=timezone.now(),
            checkout_initialization_token=token2,
            idempotency_key=str(uuid.uuid4())
        )
        from apps.payments.services import MarketplaceCheckoutService
        res = MarketplaceCheckoutService.apply_provider_result(
            tx.id, token1, provider_result={"checkout_url": "https://www.sandbox.paypal.com/approve/123", "provider_payment_id": "123", "raw_response": {}}
        )
        tx.refresh_from_db()
        self.assertEqual(tx.checkout_state, PaymentTransaction.CheckoutState.INITIALIZING)
        self.assertEqual(tx.checkout_url, "")

    @override_settings(
        PAYMENT_PROVIDER='paypal',
        PAYPAL_ORDERS_CLIENT_ID='dummy_id',
        PAYPAL_ORDERS_CLIENT_SECRET='dummy_secret'
    )
    def test_temporary_provider_error_remains_retryable(self):
        token = uuid.uuid4()
        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider="paypal",
            amount=self.order.price_agreed,
            currency="KZT",
            checkout_state=PaymentTransaction.CheckoutState.INITIALIZING,
            checkout_initialization_token=token,
            idempotency_key=str(uuid.uuid4())
        )
        from apps.payments.services import MarketplaceCheckoutService
        from apps.payments.exceptions import PaymentProviderTemporaryError
        MarketplaceCheckoutService.apply_provider_result(
            tx.id, token, error=PaymentProviderTemporaryError("paypal_timeout")
        )
        tx.refresh_from_db()
        self.assertEqual(tx.checkout_state, PaymentTransaction.CheckoutState.RETRYABLE_ERROR)
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)

    @override_settings(
        PAYMENT_PROVIDER='paypal',
        PAYPAL_ORDERS_CLIENT_ID='dummy_id',
        PAYPAL_ORDERS_CLIENT_SECRET='dummy_secret'
    )
    def test_terminal_provider_state_closes_transaction(self):
        token = uuid.uuid4()
        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider="paypal",
            amount=self.order.price_agreed,
            currency="KZT",
            checkout_state=PaymentTransaction.CheckoutState.INITIALIZING,
            checkout_initialization_token=token,
            idempotency_key=str(uuid.uuid4())
        )
        from apps.payments.services import MarketplaceCheckoutService
        from apps.payments.exceptions import PaymentProviderResponseError
        MarketplaceCheckoutService.apply_provider_result(
            tx.id, token, error=PaymentProviderResponseError("paypal_terminal_order_state")
        )
        tx.refresh_from_db()
        self.assertEqual(tx.checkout_state, PaymentTransaction.CheckoutState.TERMINAL_ERROR)
        self.assertEqual(tx.status, PaymentTransaction.Status.FAILED)

    @override_settings(
        PAYMENT_PROVIDER='paypal',
        PAYPAL_ORDERS_CLIENT_ID='dummy_id',
        PAYPAL_ORDERS_CLIENT_SECRET='dummy_secret'
    )
    def test_can_retry_and_can_continue_combinations(self):
        self.client.force_authenticate(user=self.client_user)
        
        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider="paypal",
            amount=self.order.price_agreed,
            currency="KZT",
            status=PaymentTransaction.Status.SUCCESS,
            checkout_state=PaymentTransaction.CheckoutState.COMPLETED,
            idempotency_key=str(uuid.uuid4())
        )
        self.order.payment_status = Order.PaymentStatus.PAID
        self.order.save()
        
        response = self.client.get(f"/api/v1/payments/orders/{self.order.id}/status/")
        self.assertEqual(response.data["active_transaction"]["can_continue"], False)
        self.assertEqual(response.data["active_transaction"]["can_retry"], False)
        
        self.order.payment_status = Order.PaymentStatus.UNPAID
        self.order.save()
        tx.status = PaymentTransaction.Status.FAILED
        tx.checkout_state = PaymentTransaction.CheckoutState.TERMINAL_ERROR
        tx.save()
        
        response = self.client.get(f"/api/v1/payments/orders/{self.order.id}/status/")
        self.assertEqual(response.data["active_transaction"]["can_continue"], False)
        self.assertEqual(response.data["active_transaction"]["can_retry"], True)

    @override_settings(
        PAYMENT_PROVIDER='paypal',
        PAYPAL_ORDERS_CLIENT_ID='dummy_id',
        PAYPAL_ORDERS_CLIENT_SECRET='dummy_secret'
    )
    def test_return_token_cannot_capture_another_clients_order(self):
        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider="paypal",
            amount=self.order.price_agreed,
            currency="KZT",
            provider_payment_id="PAYPAL_ORDER_UNOWNED",
            status=PaymentTransaction.Status.PENDING,
            idempotency_key=str(uuid.uuid4())
        )
        self.client.force_authenticate(user=self.other_user)
        response = self.client.post("/api/v1/payments/paypal/capture/", {"paypal_order_id": "PAYPAL_ORDER_UNOWNED"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ExtractApprovalUrlTests(TestCase):
    """Tests for extract_paypal_approval_url helper."""

    def test_approve_link_extracted(self):
        """approve rel is extracted and validated."""
        from apps.payments.url_helpers import extract_paypal_approval_url
        links = [
            {"rel": "self", "href": "https://api-m.sandbox.paypal.com/v2/checkout/orders/123"},
            {"rel": "approve", "href": "https://www.sandbox.paypal.com/checkoutnow?token=XYZ"},
        ]
        url = extract_paypal_approval_url(links)
        self.assertEqual(url, "https://www.sandbox.paypal.com/checkoutnow?token=XYZ")

    def test_payer_action_link_extracted(self):
        """payer-action rel is accepted when approve is absent."""
        from apps.payments.url_helpers import extract_paypal_approval_url
        links = [
            {"rel": "self", "href": "https://api-m.sandbox.paypal.com/v2/checkout/orders/123"},
            {"rel": "payer-action", "href": "https://www.sandbox.paypal.com/checkoutnow?token=ABC"},
        ]
        url = extract_paypal_approval_url(links)
        self.assertEqual(url, "https://www.sandbox.paypal.com/checkoutnow?token=ABC")

    def test_approve_preferred_over_payer_action(self):
        """approve is preferred when both rels present."""
        from apps.payments.url_helpers import extract_paypal_approval_url
        links = [
            {"rel": "payer-action", "href": "https://www.sandbox.paypal.com/payer-action?token=PAYER"},
            {"rel": "approve", "href": "https://www.sandbox.paypal.com/approve?token=APPROVE"},
        ]
        url = extract_paypal_approval_url(links)
        self.assertEqual(url, "https://www.sandbox.paypal.com/approve?token=APPROVE")

    def test_no_supported_approval_link_raises(self):
        """ValueError raised when no approve or payer-action link present."""
        from apps.payments.url_helpers import extract_paypal_approval_url
        links = [
            {"rel": "self", "href": "https://api-m.sandbox.paypal.com/v2/checkout/orders/123"},
            {"rel": "capture", "href": "https://api-m.sandbox.paypal.com/v2/checkout/orders/123/capture"},
        ]
        with self.assertRaises(ValueError):
            extract_paypal_approval_url(links)

    def test_unsafe_url_rejected(self):
        """approve link with non-PayPal hostname is rejected."""
        from apps.payments.url_helpers import extract_paypal_approval_url
        links = [
            {"rel": "approve", "href": "https://evil.example.com/checkoutnow?token=XYZ"},
        ]
        with self.assertRaises(ValueError):
            extract_paypal_approval_url(links)

    def test_http_url_rejected(self):
        """approve link with HTTP scheme is rejected."""
        from apps.payments.url_helpers import extract_paypal_approval_url
        links = [
            {"rel": "approve", "href": "http://www.sandbox.paypal.com/checkoutnow?token=XYZ"},
        ]
        with self.assertRaises(ValueError):
            extract_paypal_approval_url(links)

    def test_empty_links_raises(self):
        """Empty links list raises ValueError."""
        from apps.payments.url_helpers import extract_paypal_approval_url
        with self.assertRaises(ValueError):
            extract_paypal_approval_url([])
