from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import ProviderProfile
from apps.catalog.models import Category, Service
from apps.marketplace.models import EventRequest, Offer, Order
from apps.marketplace.utils import get_order_qr_capabilities
from apps.notifications.models import Notification as NotificationModel
from apps.payments.models import PaymentTransaction
from django.utils import timezone
from datetime import timedelta
import jwt
import hashlib
from django.conf import settings
from unittest.mock import patch

User = get_user_model()


class OrderQRTestCase(TransactionTestCase):
    """Test suite for order QR code permissions, capabilities, and actions"""

    def setUp(self):
        # Create client owner
        self.client_user = User.objects.create_user(
            email='client_owner@test.com',
            password='TestPassword123!',
            role='client'
        )
        # Create other client (stranger)
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
        # Create other provider
        self.other_provider_user = User.objects.create_user(
            email='other_provider@test.com',
            password='TestPassword123!',
            role='provider'
        )
        self.other_provider_profile = ProviderProfile.objects.create(
            user=self.other_provider_user
        )
        # Create staff user
        self.staff_user = User.objects.create_user(
            email='staff@test.com',
            password='TestPassword123!',
            is_staff=True
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

        # Create confirmed PAID order
        self.paid_order = Order.objects.create(
            offer=self.offer,
            client=self.client_user,
            provider_profile=self.provider_profile,
            status=Order.Status.CONFIRMED,
            payment_status=Order.PaymentStatus.PAID,
            price_agreed=135000,
            service_snapshot={}
        )

        # Create another request and offer for unpaid order
        self.unpaid_request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            title='My Other Decor',
            city='Алматы',
            event_date=event_date + timedelta(days=1),
            budget_min=100000,
            budget_max=150000,
            status=EventRequest.Status.OFFERS
        )
        self.unpaid_offer = Offer.objects.create(
            request=self.unpaid_request,
            service=self.service,
            provider_profile=self.provider_profile,
            price=135000,
            cover_letter='Other offer.',
            status=Offer.Status.SENT
        )

        # Create UNPAID order
        self.unpaid_order = Order.objects.create(
            offer=self.unpaid_offer,
            client=self.client_user,
            provider_profile=self.provider_profile,
            status=Order.Status.CONFIRMED,
            payment_status=Order.PaymentStatus.UNPAID,
            price_agreed=135000,
            service_snapshot={}
        )

        # Clients APIs
        self.client_api = APIClient()
        self.client_api.force_authenticate(user=self.client_user)

        self.other_client_api = APIClient()
        self.other_client_api.force_authenticate(user=self.other_client_user)

        self.provider_api = APIClient()
        self.provider_api.force_authenticate(user=self.provider_user)

        self.other_provider_api = APIClient()
        self.other_provider_api.force_authenticate(user=self.other_provider_user)

        self.staff_api = APIClient()
        self.staff_api.force_authenticate(user=self.staff_user)

    def test_capabilities_anonymous_and_none_users(self):
        """Anonymous and None users receive all False capabilities"""
        caps_none = get_order_qr_capabilities(self.paid_order, None)
        for val in caps_none.values():
            self.assertFalse(val)

        caps_anon = get_order_qr_capabilities(self.paid_order, AnonymousUser())
        for val in caps_anon.values():
            self.assertFalse(val)

    def test_capabilities_staff_non_participant(self):
        """Staff user who is not a participant receives all False capabilities"""
        caps = get_order_qr_capabilities(self.paid_order, self.staff_user)
        for key, val in caps.items():
            self.assertFalse(val, f"Staff capability {key} must be False")

    def test_capabilities_client_owner_paid_confirmed(self):
        """Paid confirmed order client owner can generate start QR"""
        caps = get_order_qr_capabilities(self.paid_order, self.client_user)
        self.assertTrue(caps['is_client_owner'])
        self.assertTrue(caps['can_generate_start'])
        self.assertFalse(caps['can_generate_finish'])

    def test_capabilities_client_owner_unpaid(self):
        """Unpaid order client owner cannot generate start QR"""
        caps = get_order_qr_capabilities(self.unpaid_order, self.client_user)
        self.assertTrue(caps['is_client_owner'])
        self.assertFalse(caps['can_generate_start'])

    def test_capabilities_client_owner_paid_in_progress(self):
        """Paid in progress order client owner can generate finish QR"""
        self.paid_order.status = Order.Status.IN_PROGRESS
        self.paid_order.save()
        caps = get_order_qr_capabilities(self.paid_order, self.client_user)
        self.assertTrue(caps['is_client_owner'])
        self.assertFalse(caps['can_generate_start'])
        self.assertTrue(caps['can_generate_finish'])

    def test_capabilities_provider_permissions(self):
        """Assigned provider capabilities mapping"""
        caps = get_order_qr_capabilities(self.paid_order, self.provider_user)
        self.assertTrue(caps['is_assigned_provider'])
        self.assertTrue(caps['can_check_in'])
        self.assertFalse(caps['can_complete'])
        self.assertFalse(caps['can_generate_start'])

        self.paid_order.status = Order.Status.IN_PROGRESS
        self.paid_order.save()
        caps2 = get_order_qr_capabilities(self.paid_order, self.provider_user)
        self.assertTrue(caps2['can_complete'])
        self.assertFalse(caps2['can_check_in'])

    def test_unrelated_provider_has_no_capabilities(self):
        """Unrelated provider receives no order capabilities"""
        caps = get_order_qr_capabilities(self.paid_order, self.other_provider_user)
        for key, val in caps.items():
            self.assertFalse(val, f"Other provider capability {key} must be False")

    def test_detail_serializer_context_none(self):
        """Serializer behaves safely when context request is missing"""
        from apps.marketplace.serializers import OrderDetailSerializer
        serializer = OrderDetailSerializer(self.paid_order)
        # Should not raise any error, and caps must be all False
        caps = serializer.data['qr_capabilities']
        for val in caps.values():
            self.assertFalse(val)

    def test_get_qr_code_security_unrelated_client(self):
        """Unrelated client receives 404 for QR generation"""
        url = f'/api/v1/orders/{self.paid_order.id}/qr-code/?type=start'
        response = self.other_client_api.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['code'], 'qr_not_available')

    def test_get_qr_code_security_assigned_provider(self):
        """Assigned provider receives 404 for QR generation"""
        url = f'/api/v1/orders/{self.paid_order.id}/qr-code/?type=start'
        response = self.provider_api.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['code'], 'qr_not_available')

    def test_get_qr_code_security_unpaid_order(self):
        """Unpaid order owner receives 403 order_not_paid"""
        url = f'/api/v1/orders/{self.unpaid_order.id}/qr-code/?type=start'
        response = self.client_api.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['code'], 'order_not_paid')

    def test_get_qr_code_security_invalid_status(self):
        """Invalid status returns 400 invalid_order_status"""
        self.paid_order.status = Order.Status.IN_PROGRESS
        self.paid_order.save()
        url = f'/api/v1/orders/{self.paid_order.id}/qr-code/?type=start'
        response = self.client_api.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['code'], 'invalid_order_status')

    def test_get_qr_code_security_invalid_type(self):
        """Invalid type parameter returns 400 invalid_qr_type"""
        url = f'/api/v1/orders/{self.paid_order.id}/qr-code/?type=unknown'
        response = self.client_api.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['code'], 'invalid_qr_type')

    def test_second_generation_invalidates_first_token(self):
        """Generating a second QR token invalidates the first token hash"""
        url = f'/api/v1/orders/{self.paid_order.id}/qr-code/?type=start'
        resp1 = self.client_api.get(url)
        token1 = resp1.data['token']

        resp2 = self.client_api.get(url)
        token2 = resp2.data['token']

        # Verify first token fails verification
        self.paid_order.refresh_from_db()
        token_hash1 = hashlib.sha256(token1.encode('utf-8')).hexdigest()
        token_hash2 = hashlib.sha256(token2.encode('utf-8')).hexdigest()

        self.assertNotEqual(self.paid_order.qr_start_token_hash, token_hash1)
        self.assertEqual(self.paid_order.qr_start_token_hash, token_hash2)

    def test_check_in_wrong_provider_returns_404(self):
        """Unrelated provider check-in returns 404"""
        url = f'/api/v1/orders/{self.paid_order.id}/qr-code/?type=start'
        resp = self.client_api.get(url)
        token = resp.data['token']

        url_checkin = f'/api/v1/orders/{self.paid_order.id}/actions/check-in/'
        resp_checkin = self.other_provider_api.post(url_checkin, {"token": token})
        self.assertEqual(resp_checkin.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp_checkin.data['code'], 'qr_not_available')

    def test_check_in_invalid_or_expired_tokens(self):
        """Token verification failures map to accurate machine readable codes"""
        # 1. Expired token
        exp = timezone.now() - timedelta(minutes=1)
        payload = {
            'order_id': self.paid_order.id,
            'type': 'start',
            'nonce': 'abc',
            'exp': int(exp.timestamp())
        }
        expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

        url_checkin = f'/api/v1/orders/{self.paid_order.id}/actions/check-in/'
        resp_expired = self.provider_api.post(url_checkin, {"token": expired_token})
        self.assertEqual(resp_expired.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp_expired.data['code'], 'qr_token_expired')

        # 2. Token wrong order
        payload_wrong_order = {
            'order_id': 9999,
            'type': 'start',
            'nonce': 'abc',
            'exp': int((timezone.now() + timedelta(minutes=5)).timestamp())
        }
        token_wrong_order = jwt.encode(payload_wrong_order, settings.SECRET_KEY, algorithm='HS256')
        resp_wrong_order = self.provider_api.post(url_checkin, {"token": token_wrong_order})
        self.assertEqual(resp_wrong_order.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp_wrong_order.data['code'], 'qr_token_wrong_order')

        # 3. Token wrong type (Finish token submitted to checkin)
        payload_wrong_type = {
            'order_id': self.paid_order.id,
            'type': 'finish',
            'nonce': 'abc',
            'exp': int((timezone.now() + timedelta(minutes=5)).timestamp())
        }
        token_wrong_type = jwt.encode(payload_wrong_type, settings.SECRET_KEY, algorithm='HS256')
        resp_wrong_type = self.provider_api.post(url_checkin, {"token": token_wrong_type})
        self.assertEqual(resp_wrong_type.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp_wrong_type.data['code'], 'qr_token_wrong_type')

    def test_replaced_or_reused_token_hash_mismatch(self):
        """Token hash mismatch returns qr_token_replaced"""
        url = f'/api/v1/orders/{self.paid_order.id}/qr-code/?type=start'
        resp1 = self.client_api.get(url)
        token1 = resp1.data['token']

        # Generate second token, invalidating the first
        self.client_api.get(url)

        # Attempt to scan first token
        url_checkin = f'/api/v1/orders/{self.paid_order.id}/actions/check-in/'
        resp = self.provider_api.post(url_checkin, {"token": token1})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data['code'], 'qr_token_replaced')

    def test_successful_start_transitions_order_schedules_one_notification(self):
        """Successful check-in transitions order, clears token hash, schedules one notification, and does not alter payments"""
        url = f'/api/v1/orders/{self.paid_order.id}/qr-code/?type=start'
        resp = self.client_api.get(url)
        token = resp.data['token']

        # Record payment status to assert no changes
        initial_payment_status = self.paid_order.payment_status

        url_checkin = f'/api/v1/orders/{self.paid_order.id}/actions/check-in/'
        
        # Test notification count (exactly 1)
        with patch('apps.marketplace.views.safe_create_notification') as mock_notify:
            resp_checkin = self.provider_api.post(url_checkin, {"token": token})
            self.assertEqual(resp_checkin.status_code, status.HTTP_200_OK)
            mock_notify.assert_called_once()

        self.paid_order.refresh_from_db()
        self.assertEqual(self.paid_order.status, Order.Status.IN_PROGRESS)
        self.assertEqual(self.paid_order.qr_start_token_hash, '')
        self.assertEqual(self.paid_order.payment_status, initial_payment_status)

        # Repeated scans should fail safely without creating additional notifications
        with patch('apps.marketplace.views.safe_create_notification') as mock_notify2:
            resp_repeat = self.provider_api.post(url_checkin, {"token": token})
            self.assertEqual(resp_repeat.status_code, status.HTTP_400_BAD_REQUEST)
            mock_notify2.assert_not_called()

    def test_successful_complete_transitions_order(self):
        """Successful completion transitions order and schedules notification"""
        # Put order in progress first
        self.paid_order.status = Order.Status.IN_PROGRESS
        self.paid_order.save()

        url = f'/api/v1/orders/{self.paid_order.id}/qr-code/?type=finish'
        resp = self.client_api.get(url)
        token = resp.data['token']

        url_complete = f'/api/v1/orders/{self.paid_order.id}/actions/complete/'
        
        with patch('apps.marketplace.views.safe_create_notification') as mock_notify:
            resp_complete = self.provider_api.post(url_complete, {"token": token})
            self.assertEqual(resp_complete.status_code, status.HTTP_200_OK)
            self.assertEqual(mock_notify.call_count, 2)  # notify provider & client

        self.paid_order.refresh_from_db()
        self.assertEqual(self.paid_order.status, Order.Status.COMPLETED)
        self.assertEqual(self.paid_order.qr_finish_token_hash, '')
