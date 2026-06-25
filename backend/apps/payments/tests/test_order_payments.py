from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import ProviderProfile
from apps.catalog.models import Category, Service
from apps.marketplace.models import EventRequest, Offer, Order
from apps.payments.models import PaymentTransaction
from apps.payments.adapters import get_payment_adapter, MockPaymentAdapter
from datetime import timedelta
from django.utils import timezone
from django.conf import settings

User = get_user_model()


class OrderPaymentsTestCase(TestCase):
    """Test suite for marketplace order payment core and mock provider adapter"""

    def setUp(self):
        # Create client owner
        self.client_user = User.objects.create_user(
            email='client_owner@test.com',
            password='TestPassword123!',
            role='client'
        )
        # Create another client
        self.other_client_user = User.objects.create_user(
            email='other_client@test.com',
            password='TestPassword123!',
            role='client'
        )
        # Create provider
        self.provider_user = User.objects.create_user(
            email='provider@test.com',
            password='TestPassword123!',
            role='provider'
        )
        self.provider_profile = ProviderProfile.objects.create(
            user=self.provider_user
        )

        # Create catalog category and service
        self.category = Category.objects.create(
            name_ru='Декор',
            name_en='Decor',
            slug='decor'
        )
        self.service = Service.objects.create(
            provider=self.provider_profile,
            category=self.category,
            title='Wedding Decoration',
            price_amount=120000,
            price_type='event',
            city='Алматы'
        )

        # Create event request
        event_date = timezone.now() + timedelta(days=14)
        self.request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            title='My Wedding Decor',
            city='Алматы',
            event_date=event_date,
            budget_min=100000,
            budget_max=150000,
            status=EventRequest.Status.OFFERS
        )

        # Create offer
        self.offer = Offer.objects.create(
            request=self.request,
            service=self.service,
            provider_profile=self.provider_profile,
            price=135000,
            cover_letter='We offer premium floral design.',
            status=Offer.Status.SENT
        )

        # Create confirmed unpaid order from accepted offer
        self.order = Order.objects.create(
            offer=self.offer,
            client=self.client_user,
            provider_profile=self.provider_profile,
            status=Order.Status.CONFIRMED,
            payment_status=Order.PaymentStatus.UNPAID,
            price_agreed=135000,
            service_snapshot={}
        )

        # API Clients
        self.client_api = APIClient()
        self.client_api.force_authenticate(user=self.client_user)

        self.other_client_api = APIClient()
        self.other_client_api.force_authenticate(user=self.other_client_user)

        self.provider_api = APIClient()
        self.provider_api.force_authenticate(user=self.provider_user)

        self.anon_api = APIClient()

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_MOCK_ENABLED=True)
    def test_client_owner_can_create_payment_transaction(self):
        """1. Client owner can create payment transaction for unpaid confirmed order."""
        url = f'/api/v1/payments/orders/{self.order.id}/create/'
        response = self.client_api.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('transaction_id', response.data)
        self.assertEqual(response.data['status'], 'pending')
        self.assertEqual(response.data['provider'], 'mock')
        self.assertEqual(float(response.data['amount']), 135000.00)
        self.assertEqual(response.data['currency'], 'KZT')
        self.assertTrue(response.data['checkout_url'].startswith('http'))

        # Check database record
        tx = PaymentTransaction.objects.get(pk=response.data['transaction_id'])
        self.assertEqual(tx.order, self.order)
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_MOCK_ENABLED=True)
    def test_other_client_cannot_create_payment(self):
        """2. Other client cannot create payment."""
        url = f'/api/v1/payments/orders/{self.order.id}/create/'
        response = self.other_client_api.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_MOCK_ENABLED=True)
    def test_provider_cannot_create_payment(self):
        """3. Provider cannot create payment."""
        url = f'/api/v1/payments/orders/{self.order.id}/create/'
        response = self.provider_api.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_MOCK_ENABLED=True)
    def test_anonymous_cannot_create_payment(self):
        """4. Anonymous cannot create payment."""
        url = f'/api/v1/payments/orders/{self.order.id}/create/'
        response = self.anon_api.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_MOCK_ENABLED=True)
    def test_cannot_create_payment_for_already_paid_order(self):
        """5. Cannot create payment for already paid order."""
        self.order.payment_status = Order.PaymentStatus.PAID
        self.order.save()

        url = f'/api/v1/payments/orders/{self.order.id}/create/'
        response = self.client_api.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already been paid", response.data['detail'])

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_MOCK_ENABLED=True)
    def test_cannot_create_payment_for_cancelled_or_invalid_order(self):
        """6. Cannot create payment for cancelled/invalid order if such status exists."""
        self.order.status = Order.Status.CANCELLED
        self.order.save()

        url = f'/api/v1/payments/orders/{self.order.id}/create/'
        response = self.client_api.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Only CONFIRMED orders can be paid", response.data['detail'])

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_MOCK_ENABLED=True)
    def test_amount_taken_from_price_agreed_not_payload(self):
        """7. Amount is taken from order.price_agreed, not request payload."""
        url = f'/api/v1/payments/orders/{self.order.id}/create/'
        response = self.client_api.post(url, {'amount': 5000})  # Try to manipulate amount
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(response.data['amount']), 135000.00)  # Should remain 135000

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_MOCK_ENABLED=True)
    def test_pending_transaction_reused_on_repeated_create(self):
        """8. Pending transaction is reused for repeated create calls."""
        url = f'/api/v1/payments/orders/{self.order.id}/create/'
        response1 = self.client_api.post(url)
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        tx_id_1 = response1.data['transaction_id']

        response2 = self.client_api.post(url)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        tx_id_2 = response2.data['transaction_id']

        self.assertEqual(tx_id_1, tx_id_2)
        self.assertEqual(PaymentTransaction.objects.filter(order=self.order).count(), 1)

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_MOCK_ENABLED=True)
    def test_status_endpoint_returns_order_status_and_latest_transaction(self):
        """9. Status endpoint returns order payment status and latest transaction."""
        url_create = f'/api/v1/payments/orders/{self.order.id}/create/'
        self.client_api.post(url_create)

        url_status = f'/api/v1/payments/orders/{self.order.id}/status/'
        response = self.client_api.post(url_create)  # Get tx details
        tx_id = response.data['transaction_id']

        # Call GET status
        response_status = self.client_api.get(url_status)
        self.assertEqual(response_status.status_code, status.HTTP_200_OK)
        self.assertEqual(response_status.data['order_id'], self.order.id)
        self.assertEqual(response_status.data['order_payment_status'], 'unpaid')
        self.assertEqual(response_status.data['latest_transaction']['id'], tx_id)
        self.assertEqual(response_status.data['latest_transaction']['status'], 'pending')

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_MOCK_ENABLED=True)
    def test_status_endpoint_does_not_expose_raw_response_or_secrets(self):
        """10. Status endpoint does not expose raw_response or secrets."""
        url_create = f'/api/v1/payments/orders/{self.order.id}/create/'
        create_resp = self.client_api.post(url_create)
        tx_id = create_resp.data['transaction_id']

        tx = PaymentTransaction.objects.get(pk=tx_id)
        tx.raw_response = {"secret_token": "highly-sensitive-token", "card": "4111"}
        tx.save()

        url_status = f'/api/v1/payments/orders/{self.order.id}/status/'
        response = self.client_api.get(url_status)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Ensure raw_response or secrets are not in the response payload
        serialized_tx = response.data['latest_transaction']
        self.assertNotIn('raw_response', serialized_tx)
        self.assertNotIn('secret', str(response.data))

    @override_settings(PAYMENT_PROVIDER='mock')
    def test_payment_provider_mock_uses_mock_adapter(self):
        """11. PAYMENT_PROVIDER=mock uses MockPaymentAdapter."""
        adapter = get_payment_adapter()
        self.assertIsInstance(adapter, MockPaymentAdapter)

    @override_settings(DEBUG=True, PAYMENT_MOCK_ENABLED=True)
    def test_existing_mock_pay_works_under_debug_and_mock_enabled(self):
        """12. Existing mock-pay works under DEBUG=True and PAYMENT_MOCK_ENABLED=True."""
        url = f'/api/v1/orders/{self.order.id}/actions/mock-pay/'
        response = self.client_api.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'paid')

        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)

    @override_settings(DEBUG=False, PAYMENT_MOCK_ENABLED=True)
    def test_existing_mock_pay_blocked_when_debug_false(self):
        """13a. Existing mock-pay is blocked when DEBUG=False."""
        url = f'/api/v1/orders/{self.order.id}/actions/mock-pay/'
        response = self.client_api.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(DEBUG=True, PAYMENT_MOCK_ENABLED=False)
    def test_existing_mock_pay_blocked_when_mock_disabled(self):
        """13b. Existing mock-pay is blocked when PAYMENT_MOCK_ENABLED=False."""
        url = f'/api/v1/orders/{self.order.id}/actions/mock-pay/'
        response = self.client_api.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_MOCK_ENABLED=True)
    def test_qr_blocked_while_transaction_is_pending_and_unpaid(self):
        """14. QR remains blocked while transaction is pending and order.payment_status is unpaid."""
        # Create a pending payment transaction
        url_create = f'/api/v1/payments/orders/{self.order.id}/create/'
        self.client_api.post(url_create)

        # Check order payment status remains unpaid
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.UNPAID)

        # Try to access QR code
        url_qr = f'/api/v1/orders/{self.order.id}/qr-code/?type=start'
        response_qr = self.client_api.get(url_qr)
        self.assertEqual(response_qr.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Payment required", response_qr.data['detail'])

    @override_settings(DEBUG=True, PAYMENT_MOCK_ENABLED=True)
    def test_qr_unlocks_only_after_order_is_paid_via_mock_pay(self):
        """15. QR unlocks only after order.payment_status is paid via existing mock-pay."""
        # Unpaid: QR blocked
        url_qr = f'/api/v1/orders/{self.order.id}/qr-code/?type=start'
        response_qr = self.client_api.get(url_qr)
        self.assertEqual(response_qr.status_code, status.HTTP_403_FORBIDDEN)

        # Pay order via mock-pay
        url_pay = f'/api/v1/orders/{self.order.id}/actions/mock-pay/'
        pay_response = self.client_api.post(url_pay)
        self.assertEqual(pay_response.status_code, status.HTTP_200_OK)

        # QR should now be unlocked (HTTP 200)
        response_qr_after = self.client_api.get(url_qr)
        self.assertEqual(response_qr_after.status_code, status.HTTP_200_OK)
        self.assertIn('token', response_qr_after.data)

    def _generate_signature(self, body_bytes, secret):
        import hmac
        import hashlib
        return hmac.new(
            secret.encode('utf-8'),
            body_bytes,
            hashlib.sha256
        ).hexdigest()

    def _send_webhook(self, provider, payload, secret="test-webhook-secret"):
        import json
        url = f'/api/v1/payments/webhook/{provider}/'
        body_str = json.dumps(payload)
        body_bytes = body_str.encode('utf-8')
        sig = self._generate_signature(body_bytes, secret)
        return self.anon_api.post(
            url,
            data=body_str,
            content_type='application/json',
            HTTP_X_PAYMENT_SIGNATURE=sig
        )

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_WEBHOOK_SECRET='test-webhook-secret')
    def test_valid_success_webhook_updates_transaction_and_order(self):
        """1, 2, 3. Valid success webhook marks transaction success, order paid, and unlocks QR."""
        # Create pending transaction
        url_create = f'/api/v1/payments/orders/{self.order.id}/create/'
        create_resp = self.client_api.post(url_create)
        tx_id = create_resp.data['transaction_id']

        payload = {
            "transaction_id": tx_id,
            "provider_reference": "ref-123",
            "status": "success",
            "amount": "135000.00",
            "currency": "KZT"
        }

        response = self._send_webhook("mock", payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['ok'])
        self.assertEqual(response.data['status'], 'success')

        # Check transaction state
        tx = PaymentTransaction.objects.get(pk=tx_id)
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCESS)
        self.assertIsNotNone(tx.paid_at)
        self.assertEqual(tx.provider_reference, "ref-123")

        # Check order state
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)

        # QR should unlock
        url_qr = f'/api/v1/orders/{self.order.id}/qr-code/?type=start'
        response_qr = self.client_api.get(url_qr)
        self.assertEqual(response_qr.status_code, 200)

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_WEBHOOK_SECRET='test-webhook-secret')
    def test_duplicate_webhook_is_idempotent(self):
        """4, 5. Duplicate success webhook returns 200, does not double-update paid_at, and does not duplicate notifications."""
        from apps.notifications.models import Notification
        
        # Create pending transaction
        url_create = f'/api/v1/payments/orders/{self.order.id}/create/'
        create_resp = self.client_api.post(url_create)
        tx_id = create_resp.data['transaction_id']

        payload = {
            "transaction_id": tx_id,
            "provider_reference": "ref-123",
            "status": "success",
            "amount": "135000.00",
            "currency": "KZT"
        }

        # Clear notifications first to count cleanly
        Notification.objects.all().delete()

        # Send first webhook
        response1 = self._send_webhook("mock", payload)
        self.assertEqual(response1.status_code, 200)
        tx1 = PaymentTransaction.objects.get(pk=tx_id)
        paid_at_1 = tx1.paid_at

        # Verify notifications triggered
        client_notifications = Notification.objects.filter(
            user=self.client_user,
            type=Notification.NotificationType.ORDER_PAID
        ).count()
        self.assertEqual(client_notifications, 1)

        # Send duplicate webhook
        response2 = self._send_webhook("mock", payload)
        self.assertEqual(response2.status_code, 200)

        # Verify no side-effects
        tx2 = PaymentTransaction.objects.get(pk=tx_id)
        self.assertEqual(tx2.paid_at, paid_at_1)

        # Verify no duplicate notifications
        client_notifications_dup = Notification.objects.filter(
            user=self.client_user,
            type=Notification.NotificationType.ORDER_PAID
        ).count()
        self.assertEqual(client_notifications_dup, 1)

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_WEBHOOK_SECRET='test-webhook-secret')
    def test_invalid_signature_rejected(self):
        """6. Invalid signature is rejected and does not modify transaction/order."""
        url_create = f'/api/v1/payments/orders/{self.order.id}/create/'
        create_resp = self.client_api.post(url_create)
        tx_id = create_resp.data['transaction_id']

        payload = {
            "transaction_id": tx_id,
            "provider_reference": "ref-123",
            "status": "success",
            "amount": "135000.00",
            "currency": "KZT"
        }

        # Send with incorrect secret signature
        response = self._send_webhook("mock", payload, secret="wrong-secret")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid webhook signature", response.data['detail'])

        # Verify no state changes
        tx = PaymentTransaction.objects.get(pk=tx_id)
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.UNPAID)

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_WEBHOOK_SECRET='test-webhook-secret')
    def test_unknown_provider_rejected(self):
        """7. Unknown provider returns 400/404 and does not modify data."""
        url_create = f'/api/v1/payments/orders/{self.order.id}/create/'
        create_resp = self.client_api.post(url_create)
        tx_id = create_resp.data['transaction_id']

        payload = {
            "transaction_id": tx_id,
            "provider_reference": "ref-123",
            "status": "success",
            "amount": "135000.00",
            "currency": "KZT"
        }

        # Send to unknown provider url path
        response = self._send_webhook("unknown_provider", payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("is not active or unknown", response.data['detail'])

        # Verify no state changes
        tx = PaymentTransaction.objects.get(pk=tx_id)
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_WEBHOOK_SECRET='test-webhook-secret')
    def test_invalid_transaction_identification_returns_404(self):
        """8. Invalid transaction id/reference returns safe 404/400."""
        import uuid
        payload = {
            "transaction_id": str(uuid.uuid4()),
            "provider_reference": "ref-123",
            "status": "success",
            "amount": "135000.00",
            "currency": "KZT"
        }
        response = self._send_webhook("mock", payload)
        self.assertEqual(response.status_code, 404)
        self.assertIn("Transaction not found", response.data['detail'])

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_WEBHOOK_SECRET='test-webhook-secret')
    def test_amount_mismatch_rejected(self):
        """9. Amount mismatch does not mark paid."""
        url_create = f'/api/v1/payments/orders/{self.order.id}/create/'
        create_resp = self.client_api.post(url_create)
        tx_id = create_resp.data['transaction_id']

        payload = {
            "transaction_id": tx_id,
            "provider_reference": "ref-123",
            "status": "success",
            "amount": "5000.00",  # Incorrect amount
            "currency": "KZT"
        }

        response = self._send_webhook("mock", payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("amount mismatch", response.data['detail'])

        # Verify no changes
        tx = PaymentTransaction.objects.get(pk=tx_id)
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.UNPAID)

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_WEBHOOK_SECRET='test-webhook-secret')
    def test_currency_mismatch_rejected(self):
        """10. Currency mismatch does not mark paid."""
        url_create = f'/api/v1/payments/orders/{self.order.id}/create/'
        create_resp = self.client_api.post(url_create)
        tx_id = create_resp.data['transaction_id']

        payload = {
            "transaction_id": tx_id,
            "provider_reference": "ref-123",
            "status": "success",
            "amount": "135000.00",
            "currency": "USD"  # Incorrect currency
        }

        response = self._send_webhook("mock", payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("currency mismatch", response.data['detail'])

        # Verify no changes
        tx = PaymentTransaction.objects.get(pk=tx_id)
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.UNPAID)

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_WEBHOOK_SECRET='test-webhook-secret')
    def test_failed_webhook_marks_failed(self):
        """11. Failed webhook marks transaction failed but QR remains locked."""
        url_create = f'/api/v1/payments/orders/{self.order.id}/create/'
        create_resp = self.client_api.post(url_create)
        tx_id = create_resp.data['transaction_id']

        payload = {
            "transaction_id": tx_id,
            "provider_reference": "ref-123",
            "status": "failed",
            "amount": "135000.00",
            "currency": "KZT"
        }

        response = self._send_webhook("mock", payload)
        self.assertEqual(response.status_code, 200)

        # Check transaction state
        tx = PaymentTransaction.objects.get(pk=tx_id)
        self.assertEqual(tx.status, PaymentTransaction.Status.FAILED)

        # Check order payment status (should become FAILED or remain UNPAID, we transition to FAILED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.FAILED)

        # QR must remain blocked
        url_qr = f'/api/v1/orders/{self.order.id}/qr-code/?type=start'
        response_qr = self.client_api.get(url_qr)
        self.assertEqual(response_qr.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_WEBHOOK_SECRET='test-webhook-secret')
    def test_cancelled_webhook_marks_cancelled(self):
        """12. Cancelled webhook marks transaction cancelled but QR remains locked."""
        url_create = f'/api/v1/payments/orders/{self.order.id}/create/'
        create_resp = self.client_api.post(url_create)
        tx_id = create_resp.data['transaction_id']

        payload = {
            "transaction_id": tx_id,
            "provider_reference": "ref-123",
            "status": "cancelled",
            "amount": "135000.00",
            "currency": "KZT"
        }

        response = self._send_webhook("mock", payload)
        self.assertEqual(response.status_code, 200)

        # Check transaction state
        tx = PaymentTransaction.objects.get(pk=tx_id)
        self.assertEqual(tx.status, PaymentTransaction.Status.CANCELLED)

        # Check order state
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.FAILED)

        # QR must remain blocked
        url_qr = f'/api/v1/orders/{self.order.id}/qr-code/?type=start'
        response_qr = self.client_api.get(url_qr)
        self.assertEqual(response_qr.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_WEBHOOK_SECRET='test-webhook-secret')
    def test_pending_webhook_does_not_mark_paid(self):
        """13. Pending webhook does not mark paid."""
        url_create = f'/api/v1/payments/orders/{self.order.id}/create/'
        create_resp = self.client_api.post(url_create)
        tx_id = create_resp.data['transaction_id']

        payload = {
            "transaction_id": tx_id,
            "provider_reference": "ref-123",
            "status": "pending",
            "amount": "135000.00",
            "currency": "KZT"
        }

        response = self._send_webhook("mock", payload)
        self.assertEqual(response.status_code, 200)

        # Check transaction state (still pending)
        tx = PaymentTransaction.objects.get(pk=tx_id)
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)

        # Check order state
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.UNPAID)

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_WEBHOOK_SECRET='test-webhook-secret')
    def test_webhook_response_does_not_expose_raw_response_or_secrets(self):
        """14. Webhook response does not expose raw_response/secrets."""
        url_create = f'/api/v1/payments/orders/{self.order.id}/create/'
        create_resp = self.client_api.post(url_create)
        tx_id = create_resp.data['transaction_id']

        payload = {
            "transaction_id": tx_id,
            "provider_reference": "ref-123",
            "status": "success",
            "amount": "135000.00",
            "currency": "KZT"
        }

        response = self._send_webhook("mock", payload)
        self.assertEqual(response.status_code, 200)
        
        # Verify fields in response payload
        self.assertNotIn('raw_response', response.data)
        self.assertNotIn('secret', str(response.data))

    @override_settings(PAYMENT_PROVIDER='mock', PAYMENT_WEBHOOK_SECRET='test-webhook-secret')
    def test_payment_status_endpoint_reflects_webhook_success_and_failure(self):
        """15. Payment status endpoint reflects webhook success/failure."""
        url_create = f'/api/v1/payments/orders/{self.order.id}/create/'
        create_resp = self.client_api.post(url_create)
        tx_id = create_resp.data['transaction_id']

        url_status = f'/api/v1/payments/orders/{self.order.id}/status/'

        # Webhook: failed
        payload_fail = {
            "transaction_id": tx_id,
            "provider_reference": "ref-123",
            "status": "failed",
            "amount": "135000.00",
            "currency": "KZT"
        }
        self._send_webhook("mock", payload_fail)
        
        # Status check
        response1 = self.client_api.get(url_status)
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response1.data['order_payment_status'], 'failed')
        self.assertEqual(response1.data['latest_transaction']['status'], 'failed')

        # Create new transaction to try again
        new_create_resp = self.client_api.post(url_create)
        new_tx_id = new_create_resp.data['transaction_id']

        # Webhook: success
        payload_success = {
            "transaction_id": new_tx_id,
            "provider_reference": "ref-456",
            "status": "success",
            "amount": "135000.00",
            "currency": "KZT"
        }
        self._send_webhook("mock", payload_success)

        # Status check
        response2 = self.client_api.get(url_status)
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(response2.data['order_payment_status'], 'paid')
        self.assertEqual(response2.data['latest_transaction']['status'], 'success')


from decimal import Decimal
from unittest.mock import patch, MagicMock
import base64
import json
from apps.payments.adapters import CloudPaymentsAdapter

@override_settings(
    PAYMENT_PROVIDER='cloudpayments',
    PAYMENT_MOCK_ENABLED=False,
    PAYMENT_API_URL='https://api.cloudpayments.kz',
    PAYMENT_PUBLIC_KEY='test-public-id',
    PAYMENT_SECRET_KEY='test-api-secret',
    PAYMENT_WEBHOOK_SECRET='test-webhook-secret',
    PAYMENT_TIMEOUT_SECONDS=10
)
class CloudPaymentsTestCase(TestCase):
    """Test suite for CloudPayments provider adapter and webhook integration"""

    def setUp(self):
        # Create client owner
        self.client_user = User.objects.create_user(
            email='cp_client@test.com',
            password='TestPassword123!',
            role='client'
        )
        self.provider_user = User.objects.create_user(
            email='cp_provider@test.com',
            password='TestPassword123!',
            role='provider'
        )
        self.provider_profile = ProviderProfile.objects.create(
            user=self.provider_user
        )
        self.category = Category.objects.create(
            name_ru='Декор',
            name_en='Decor',
            slug='decor-cp'
        )
        self.service = Service.objects.create(
            provider=self.provider_profile,
            category=self.category,
            title='Wedding CP Decor',
            price_amount=135000,
            price_type='event',
            city='Алматы'
        )
        event_date = timezone.now() + timedelta(days=14)
        self.request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            title='Wedding CP Decor Event',
            city='Алматы',
            event_date=event_date,
            budget_min=100000,
            budget_max=150000,
            status=EventRequest.Status.OFFERS
        )
        self.offer = Offer.objects.create(
            request=self.request,
            service=self.service,
            provider_profile=self.provider_profile,
            price=135000,
            cover_letter='Wedding CP Decor cover letter',
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
        
        self.client_api = APIClient()
        self.client_api.force_authenticate(user=self.client_user)
        self.anon_api = APIClient()

    def test_payment_provider_resolves_to_cloudpayments_adapter(self):
        """1. PAYMENT_PROVIDER=cloudpayments selects CloudPaymentsAdapter."""
        adapter = get_payment_adapter()
        self.assertIsInstance(adapter, CloudPaymentsAdapter)

    @patch('urllib.request.urlopen')
    def test_create_checkout_sends_payload_and_basic_auth(self, mock_urlopen):
        """2, 3, 4, 5. create_checkout sends request with Basic Auth and parses Success response."""
        # Mock successful CloudPayments response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "Success": True,
            "Message": None,
            "Model": {
                "Id": 9876543,
                "Number": "cp-order-num-123",
                "Amount": 135000.00,
                "Currency": "KZT",
                "Url": "https://checkout.cloudpayments.kz/pay/testurl"
            }
        }).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider='cloudpayments',
            amount=self.order.price_agreed,
            currency='KZT',
            status=PaymentTransaction.Status.PENDING,
            idempotency_key='cp_test_create_checkout_key'
        )

        adapter = get_payment_adapter()
        checkout_url = adapter.create_checkout(tx)

        # Assert URL returned correctly
        self.assertEqual(checkout_url, "https://checkout.cloudpayments.kz/pay/testurl")

        # Verify urllib.urlopen was called with expected URL
        self.assertTrue(mock_urlopen.called)
        args, kwargs = mock_urlopen.call_args
        req = args[0]
        self.assertEqual(req.full_url, "https://api.cloudpayments.kz/orders/create")
        self.assertEqual(req.method, "POST")

        # Verify Basic Auth headers
        auth_header = req.get_header('Authorization')
        self.assertTrue(auth_header.startswith('Basic '))
        encoded_auth = auth_header.split(' ')[1]
        decoded_auth = base64.b64decode(encoded_auth).decode('utf-8')
        self.assertEqual(decoded_auth, "test-public-id:test-api-secret")

        # Verify Request Payload
        payload = json.loads(req.data.decode('utf-8'))
        self.assertEqual(payload['Amount'], 135000.0)
        self.assertEqual(payload['Currency'], 'KZT')
        self.assertEqual(payload['InvoiceId'], str(self.order.id))
        self.assertEqual(payload['AccountId'], str(self.order.client_id))
        self.assertEqual(payload['SendEmail'], False)

        # Verify that transaction object updated in DB
        tx.refresh_from_db()
        self.assertEqual(tx.provider_payment_id, "9876543")
        self.assertEqual(tx.provider_reference, "9876543")
        self.assertEqual(tx.raw_response, {"Number": "cp-order-num-123"})

    @patch('urllib.request.urlopen')
    def test_create_checkout_failure_raises_safe_error(self, mock_urlopen):
        """6. create_checkout failure response raises safe error, no secret leak."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "Success": False,
            "Message": "Invalid merchant status or settings"
        }).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider='cloudpayments',
            amount=self.order.price_agreed,
            currency='KZT',
            status=PaymentTransaction.Status.PENDING,
            idempotency_key='cp_test_failure_key'
        )

        adapter = get_payment_adapter()
        with self.assertRaises(RuntimeError) as ctx:
            adapter.create_checkout(tx)
        
        self.assertIn("CloudPayments API call failed", str(ctx.exception))
        # Ensure credentials/secrets are not leaked in exception string
        self.assertNotIn("test-public-id", str(ctx.exception))
        self.assertNotIn("test-api-secret", str(ctx.exception))

    @patch('urllib.request.urlopen')
    def test_create_checkout_network_failure_raises_safe_error(self, mock_urlopen):
        """7. Network failure raises safe error."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider='cloudpayments',
            amount=self.order.price_agreed,
            currency='KZT',
            status=PaymentTransaction.Status.PENDING,
            idempotency_key='cp_test_net_failure_key'
        )

        adapter = get_payment_adapter()
        with self.assertRaises(RuntimeError) as ctx:
            adapter.create_checkout(tx)
        
        self.assertIn("CloudPayments network error", str(ctx.exception))
        self.assertNotIn("test-public-id", str(ctx.exception))
        self.assertNotIn("test-api-secret", str(ctx.exception))

    def _generate_cp_signature(self, body_bytes, secret):
        import hmac
        import hashlib
        import base64
        return base64.b64encode(
            hmac.new(secret.encode('utf-8'), body_bytes, hashlib.sha256).digest()
        ).decode('utf-8')

    def _send_cp_webhook(self, payload, header_name="Content-HMAC", secret="test-webhook-secret"):
        import json
        url = '/api/v1/payments/webhook/cloudpayments/'
        body_str = json.dumps(payload)
        body_bytes = body_str.encode('utf-8')
        sig = self._generate_cp_signature(body_bytes, secret)
        
        headers = {}
        if header_name == "Content-HMAC":
            headers["HTTP_CONTENT_HMAC"] = sig
        elif header_name == "X-Content-HMAC":
            headers["HTTP_X_CONTENT_HMAC"] = sig
            
        return self.anon_api.post(
            url,
            data=body_str,
            content_type='application/json',
            **headers
        )

    def test_valid_content_hmac_webhook_success(self):
        """8, 16, 17. Valid Content-HMAC webhook marks transaction success, returns {"code": 0}, and raw_response is sanitized."""
        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider='cloudpayments',
            amount=Decimal('135000.00'),
            currency='KZT',
            status=PaymentTransaction.Status.PENDING,
            idempotency_key='cp_test_webhook_success_key',
            provider_reference='cp-tx-999'
        )

        payload = {
            "TransactionId": "cp-tx-999",
            "InvoiceId": str(self.order.id),
            "Amount": "135000.00",
            "Currency": "KZT",
            "Status": "Completed",
            "DateTime": "2026-06-12T03:00:00",
            "ReasonCode": 0,
            "CardType": "Visa",
            "CardMask": "411111XXXXXX1111",
            "PayerEmail": "sensitive@payer.com"
        }

        response = self._send_cp_webhook(payload, header_name="Content-HMAC")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"code": 0})

        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCESS)
        self.assertIsNotNone(tx.paid_at)

        # Check raw_response is sanitized
        self.assertEqual(tx.raw_response["TransactionId"], "cp-tx-999")
        self.assertEqual(tx.raw_response["InvoiceId"], str(self.order.id))
        self.assertEqual(tx.raw_response["Amount"], "135000.00")
        self.assertEqual(tx.raw_response["Currency"], "KZT")
        self.assertEqual(tx.raw_response["Status"], "Completed")
        self.assertIn("DateTime", tx.raw_response)
        
        # PII and metadata/card data should NOT be saved in raw_response
        self.assertNotIn("CardType", tx.raw_response)
        self.assertNotIn("CardMask", tx.raw_response)
        self.assertNotIn("PayerEmail", tx.raw_response)
        self.assertNotIn("headers", tx.raw_response)
        self.assertNotIn("signature", str(tx.raw_response))

        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)

    def test_valid_x_content_hmac_webhook_success(self):
        """9. Valid X-Content-HMAC webhook is accepted if supported."""
        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider='cloudpayments',
            amount=Decimal('135000.00'),
            currency='KZT',
            status=PaymentTransaction.Status.PENDING,
            idempotency_key='cp_test_webhook_x_hmac_key',
            provider_reference='cp-tx-888'
        )

        payload = {
            "TransactionId": "cp-tx-888",
            "InvoiceId": str(self.order.id),
            "Amount": "135000.00",
            "Currency": "KZT",
            "Status": "Completed"
        }

        response = self._send_cp_webhook(payload, header_name="X-Content-HMAC")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"code": 0})

        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCESS)

    def test_invalid_signature_rejected(self):
        """10. Invalid signature rejected and order remains unpaid."""
        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider='cloudpayments',
            amount=Decimal('135000.00'),
            currency='KZT',
            status=PaymentTransaction.Status.PENDING,
            idempotency_key='cp_test_webhook_invalid_sig_key',
            provider_reference='cp-tx-777'
        )

        payload = {
            "TransactionId": "cp-tx-777",
            "InvoiceId": str(self.order.id),
            "Amount": "135000.00",
            "Currency": "KZT",
            "Status": "Completed"
        }

        # Send with wrong webhook secret
        response = self._send_cp_webhook(payload, header_name="Content-HMAC", secret="wrong-secret")
        self.assertEqual(response.status_code, 400)
        
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.UNPAID)

    def test_amount_mismatch_rejected(self):
        """11. Amount mismatch rejected and order remains unpaid."""
        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider='cloudpayments',
            amount=Decimal('135000.00'),
            currency='KZT',
            status=PaymentTransaction.Status.PENDING,
            idempotency_key='cp_test_webhook_amount_mismatch_key',
            provider_reference='cp-tx-666'
        )

        payload = {
            "TransactionId": "cp-tx-666",
            "InvoiceId": str(self.order.id),
            "Amount": "5000.00",  # Incorrect amount
            "Currency": "KZT",
            "Status": "Completed"
        }

        response = self._send_cp_webhook(payload, header_name="Content-HMAC")
        self.assertEqual(response.status_code, 400)
        
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)

    def test_currency_mismatch_rejected(self):
        """12. Currency mismatch rejected."""
        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider='cloudpayments',
            amount=Decimal('135000.00'),
            currency='KZT',
            status=PaymentTransaction.Status.PENDING,
            idempotency_key='cp_test_webhook_currency_mismatch_key',
            provider_reference='cp-tx-555'
        )

        payload = {
            "TransactionId": "cp-tx-555",
            "InvoiceId": str(self.order.id),
            "Amount": "135000.00",
            "Currency": "USD",  # Incorrect currency
            "Status": "Completed"
        }

        response = self._send_cp_webhook(payload, header_name="Content-HMAC")
        self.assertEqual(response.status_code, 400)
        
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)

    def test_duplicate_webhook_is_idempotent(self):
        """13. Duplicate success webhook is idempotent, returns code 0."""
        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider='cloudpayments',
            amount=Decimal('135000.00'),
            currency='KZT',
            status=PaymentTransaction.Status.PENDING,
            idempotency_key='cp_test_webhook_duplicate_key',
            provider_reference='cp-tx-444'
        )

        payload = {
            "TransactionId": "cp-tx-444",
            "InvoiceId": str(self.order.id),
            "Amount": "135000.00",
            "Currency": "KZT",
            "Status": "Completed"
        }

        # Send first time
        response1 = self._send_cp_webhook(payload, header_name="Content-HMAC")
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response1.data, {"code": 0})
        
        tx.refresh_from_db()
        paid_at_first = tx.paid_at

        # Send second time
        response2 = self._send_cp_webhook(payload, header_name="Content-HMAC")
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(response2.data, {"code": 0})

        tx.refresh_from_db()
        self.assertEqual(tx.paid_at, paid_at_first)

    def test_failed_webhook_marks_failed(self):
        """14. Failed webhook marks transaction failed and QR remains locked."""
        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider='cloudpayments',
            amount=Decimal('135000.00'),
            currency='KZT',
            status=PaymentTransaction.Status.PENDING,
            idempotency_key='cp_test_webhook_failed_key',
            provider_reference='cp-tx-333'
        )

        payload = {
            "TransactionId": "cp-tx-333",
            "InvoiceId": str(self.order.id),
            "Amount": "135000.00",
            "Currency": "KZT",
            "Status": "Failed"
        }

        response = self._send_cp_webhook(payload, header_name="Content-HMAC")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"code": 0})

        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.FAILED)
        
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.FAILED)

        # Check QR code endpoint is blocked
        url_qr = f'/api/v1/orders/{self.order.id}/qr-code/?type=start'
        response_qr = self.client_api.get(url_qr)
        self.assertEqual(response_qr.status_code, status.HTTP_403_FORBIDDEN)

    def test_cancel_webhook_marks_cancelled(self):
        """15. Cancel webhook marks transaction cancelled and QR remains locked."""
        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider='cloudpayments',
            amount=Decimal('135000.00'),
            currency='KZT',
            status=PaymentTransaction.Status.PENDING,
            idempotency_key='cp_test_webhook_cancel_key',
            provider_reference='cp-tx-222'
        )

        payload = {
            "TransactionId": "cp-tx-222",
            "InvoiceId": str(self.order.id),
            "Amount": "135000.00",
            "Currency": "KZT",
            "Status": "Cancelled"
        }

        response = self._send_cp_webhook(payload, header_name="Content-HMAC")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"code": 0})

        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.CANCELLED)
        
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.FAILED)

        # Check QR code endpoint is blocked
        url_qr = f'/api/v1/orders/{self.order.id}/qr-code/?type=start'
        response_qr = self.client_api.get(url_qr)
        self.assertEqual(response_qr.status_code, status.HTTP_403_FORBIDDEN)

    def test_lookup_by_invoice_id_works_when_transaction_id_not_sent(self):
        """Webhooks can locate transaction by InvoiceId (either as transaction UUID or order ID) if TransactionId doesn't match/exist."""
        tx = PaymentTransaction.objects.create(
            order=self.order,
            provider='cloudpayments',
            amount=Decimal('135000.00'),
            currency='KZT',
            status=PaymentTransaction.Status.PENDING,
            idempotency_key='cp_test_webhook_invoice_lookup_key'
        )

        payload = {
            "TransactionId": "cp-tx-new-111",
            "InvoiceId": str(self.order.id),
            "Amount": "135000.00",
            "Currency": "KZT",
            "Status": "Completed"
        }

        response = self._send_cp_webhook(payload, header_name="Content-HMAC")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"code": 0})

        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(tx.provider_reference, "cp-tx-new-111")
        self.assertEqual(tx.provider_payment_id, "cp-tx-new-111")


