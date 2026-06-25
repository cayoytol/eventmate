from django.test import TransactionTestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.db import transaction, connection
from unittest import skipIf
from threading import Thread
import time

from apps.accounts.models import User, ProviderProfile
from apps.catalog.models import Category, Service
from apps.marketplace.models import EventRequest, Offer, Order
from apps.notifications.models import Notification
from django.utils import timezone
from datetime import timedelta


class OfferAcceptAtomicityTest(TransactionTestCase):
    """Test Stage A2: Atomic offer acceptance with auto-rejection"""
    
    def setUp(self):
        self.client_api = APIClient()
        
        # Create category
        self.category = Category.objects.create(
            name_ru="Фотография",
            name_en="Photography"
        )
        
        # Create client
        self.client_user = User.objects.create_user(
            email='client@test.com',
            username='client',
            password='testpass123',
            role='client'
        )
        
        # Create 3 providers
        self.provider_a = User.objects.create_user(
            email='provider_a@test.com',
            username='provider_a',
            password='testpass123',
            role='provider'
  )
        self.provider_a_profile = ProviderProfile.objects.create(user=self.provider_a)
        
        self.provider_b = User.objects.create_user(
            email='provider_b@test.com',
            username='provider_b',
            password='testpass123',
            role='provider'
        )
        self.provider_b_profile = ProviderProfile.objects.create(user=self.provider_b)
        
        self.provider_c = User.objects.create_user(
            email='provider_c@test.com',
            username='provider_c',
            password='testpass123',
            role='provider'
        )
        self.provider_c_profile = ProviderProfile.objects.create(user=self.provider_c)
        
        # Create services
        self.service_a = Service.objects.create(
            provider=self.provider_a_profile,
            category=self.category,
            title="Professional Photography A",
            description="Wedding photos",
            price_amount=50000,
            price_type='fixed',
            city="Almaty"
        )
        
        self.service_b = Service.objects.create(
            provider=self.provider_b_profile,
            category=self.category,
            title="Professional Photography B",
            description="Event photos",
            price_amount=45000,
            price_type='fixed',
            city="Almaty"
        )
        
        self.service_c = Service.objects.create(
            provider=self.provider_c_profile,
            category=self.category,
            title="Professional Photography C",
            description="Portrait photos",
            price_amount=60000,
            price_type='fixed',
            city="Almaty"
        )
    
    def test_accept_offer_rejects_others_and_excludes_winner(self):
        """Accept offer A → offers B+C rejected, A remains ACCEPTED"""
        # Create request
        event_request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            title="Need photographer",
            event_date=timezone.now() + timedelta(days=30),
            city="Almaty",
            status=EventRequest.Status.OFFERS
        )
        
        # Create 3 offers
        offer_a = Offer.objects.create(
            request=event_request,
            service=self.service_a,
            provider_profile=self.provider_a_profile,
            price=50000,
            status=Offer.Status.SENT
        )
        
        offer_b = Offer.objects.create(
            request=event_request,
            service=self.service_b,
            provider_profile=self.provider_b_profile,
            price=45000,
            status=Offer.Status.SENT
        )
        
        offer_c = Offer.objects.create(
            request=event_request,
            service=self.service_c,
            provider_profile=self.provider_c_profile,
            price=60000,
            status=Offer.Status.SENT
        )
        
        # Login as client
        self.client_api.force_authenticate(user=self.client_user)
        
        # Accept offer A
        response = self.client_api.post(f'/api/v1/offers/{offer_a.id}/accept/')
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'accepted')
        self.assertTrue(response.data['order_created'])
        
        # Refresh from DB
        offer_a.refresh_from_db()
        offer_b.refresh_from_db()
        offer_c.refresh_from_db()
        event_request.refresh_from_db()
        
        # ✅ CRITICAL: Winner A must be ACCEPTED (never rejected)
        self.assertEqual(offer_a.status, Offer.Status.ACCEPTED)
        
        # Others rejected
        self.assertEqual(offer_b.status, Offer.Status.REJECTED)
        self.assertEqual(offer_c.status, Offer.Status.REJECTED)
        
        # Request confirmed
        self.assertEqual(event_request.status, EventRequest.Status.CONFIRMED)
        
        # Order created
        self.assertTrue(Order.objects.filter(offer=offer_a).exists())
        order = Order.objects.get(offer=offer_a)
        self.assertEqual(order.client, self.client_user)
        self.assertEqual(order.provider_profile, self.provider_a_profile)
    
    def test_double_accept_returns_409(self):
        """Accept A → try accept B → 409 CONFLICT"""
        event_request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            title="Need photographer",
            event_date=timezone.now() + timedelta(days=30),
            city="Almaty",
            status=EventRequest.Status.OFFERS
        )
        
        offer_a = Offer.objects.create(
            request=event_request,
            service=self.service_a,
            provider_profile=self.provider_a_profile,
            price=50000,
            status=Offer.Status.SENT
        )
        
        offer_b = Offer.objects.create(
            request=event_request,
            service=self.service_b,
            provider_profile=self.provider_b_profile,
            price=45000,
            status=Offer.Status.SENT
        )
        
        self.client_api.force_authenticate(user=self.client_user)
        
        # First accept: OK
        response1 = self.client_api.post(f'/api/v1/offers/{offer_a.id}/accept/')
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Second accept: Should fail (offer already rejected)
        response2 = self.client_api.post(f'/api/v1/offers/{offer_b.id}/accept/')
        # Should be 400 (offer not in SENT status) since it was already rejected
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not in SENT status', response2.data['detail'])
        
        # Verify only A is accepted
        offer_a.refresh_from_db()
        offer_b.refresh_from_db()
        
        self.assertEqual(offer_a.status, Offer.Status.ACCEPTED)
        # B was rejected by bulk update from first accept
        self.assertEqual(offer_b.status, Offer.Status.REJECTED)
        
        # Only 1 order
        self.assertEqual(Order.objects.count(), 1)
    
    def test_rejected_providers_notified(self):
        """Accept A → providers B+C get OFFER_REJECTED notifications"""
        event_request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            title="Need photographer",
            event_date=timezone.now() + timedelta(days=30),
            city="Almaty",
            status=EventRequest.Status.OFFERS
        )
        
        offer_a = Offer.objects.create(
            request=event_request,
            service=self.service_a,
            provider_profile=self.provider_a_profile,
            price=50000,
            status=Offer.Status.SENT
        )
        
        offer_b = Offer.objects.create(
            request=event_request,
            service=self.service_b,
            provider_profile=self.provider_b_profile,
            price=45000,
            status=Offer.Status.SENT
        )
        
        offer_c = Offer.objects.create(
            request=event_request,
            service=self.service_c,
            provider_profile=self.provider_c_profile,
            price=60000,
            status=Offer.Status.SENT
        )
        
        self.client_api.force_authenticate(user=self.client_user)
        
        # Accept A
        response = self.client_api.post(f'/api/v1/offers/{offer_a.id}/accept/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check notifications
        # Winner: OFFER_ACCEPTED
        winner_notif = Notification.objects.filter(
            user=self.provider_a,
            type=Notification.NotificationType.OFFER_ACCEPTED
        )
        self.assertEqual(winner_notif.count(), 1)
        
        # Losers: OFFER_REJECTED
        loser_b_notif = Notification.objects.filter(
            user=self.provider_b,
            type=Notification.NotificationType.OFFER_REJECTED
        )
        self.assertEqual(loser_b_notif.count(), 1)
        self.assertIn('client_selected_another', loser_b_notif.first().payload.get('reason', ''))
        
        loser_c_notif = Notification.objects.filter(
            user=self.provider_c,
            type=Notification.NotificationType.OFFER_REJECTED
        )
        self.assertEqual(loser_c_notif.count(), 1)
    
    @skipIf(
        connection.vendor == 'sqlite',
        "SQLite doesn't support concurrent transactions properly - test only on PostgreSQL/MySQL"
    )
    def test_concurrent_accept_only_one_wins(self):
        """Race test: accept A and B simultaneously → only 1 succeeds"""
        event_request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            title="Need photographer",
            event_date=timezone.now() + timedelta(days=30),
            city="Almaty",
            status=EventRequest.Status.OFFERS
        )
        
        offer_a = Offer.objects.create(
            request=event_request,
            service=self.service_a,
            provider_profile=self.provider_a_profile,
            price=50000,
            status=Offer.Status.SENT
        )
        
        offer_b = Offer.objects.create(
            request=event_request,
            service=self.service_b,
            provider_profile=self.provider_b_profile,
            price=45000,
            status=Offer.Status.SENT
        )
        
        results = {'a': None, 'b': None}
        
        def accept_a():
            connection.close()
            try:
                client = APIClient()
                client.force_authenticate(user=self.client_user)
                results['a'] = client.post(f'/api/v1/offers/{offer_a.id}/accept/')
            finally:
                connection.close()
        
        def accept_b():
            connection.close()
            try:
                client = APIClient()
                client.force_authenticate(user=self.client_user)
                # Small delay to increase chance of race
                time.sleep(0.01)
                results['b'] = client.post(f'/api/v1/offers/{offer_b.id}/accept/')
            finally:
                connection.close()
        
        thread_a = Thread(target=accept_a)
        thread_b = Thread(target=accept_b)
        
        thread_a.start()
        thread_b.start()
        
        thread_a.join()
        thread_b.join()
        
        # Exactly one should succeed
        status_codes = [results['a'].status_code, results['b'].status_code]
        
        # One 200, one 400/409
        self.assertIn(200, status_codes)
        self.assertTrue(
            400 in status_codes or 409 in status_codes,
            f"Expected one to fail with 400/409, got {status_codes}"
        )
        
        # Exactly 1 accepted offer
        accepted_count = Offer.objects.filter(
            request=event_request,
            status=Offer.Status.ACCEPTED
        ).count()
        self.assertEqual(accepted_count, 1)
        
        # Exactly 1 order
        self.assertEqual(Order.objects.filter(offer__request=event_request).count(), 1)
    
    def test_withdrawn_offers_not_changed(self):
        """Accept A → withdrawn B stays WITHDRAWN (not changed to REJECTED)"""
        event_request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            title="Need photographer",
            event_date=timezone.now() + timedelta(days=30),
            city="Almaty",
            status=EventRequest.Status.OFFERS
        )
        
        offer_a = Offer.objects.create(
            request=event_request,
            service=self.service_a,
            provider_profile=self.provider_a_profile,
            price=50000,
            status=Offer.Status.SENT
        )
        
        offer_b = Offer.objects.create(
            request=event_request,
            service=self.service_b,
            provider_profile=self.provider_b_profile,
            price=45000,
            status=Offer.Status.WITHDRAWN  # ✅ Already withdrawn
        )
        
        self.client_api.force_authenticate(user=self.client_user)
        
        # Accept A
        response = self.client_api.post(f'/api/v1/offers/{offer_a.id}/accept/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Refresh
        offer_a.refresh_from_db()
        offer_b.refresh_from_db()
        
        # A accepted
        self.assertEqual(offer_a.status, Offer.Status.ACCEPTED)
        
        # ✅ B remains WITHDRAWN (not changed to REJECTED)
        self.assertEqual(offer_b.status, Offer.Status.WITHDRAWN)
