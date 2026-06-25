"""
Tests for Order visibility after accepting offers.
Ensures provider and client can see their orders correctly.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.accounts.models import ProviderProfile
from apps.catalog.models import Category, Service
from apps.marketplace.models import EventRequest, Offer, Order
from datetime import datetime, timedelta
from django.utils import timezone

User = get_user_model()


class OrderVisibilityTestCase(TestCase):
    """Test that providers and clients can see their orders after offer acceptance"""
    
    def setUp(self):
        # Create users
        self.client_user = User.objects.create_user(
            email='client@test.com',
            password='Test1234',
            role='client'
        )
        
        self.provider_user = User.objects.create_user(
            email='provider@test.com',
            password='Test1234',
            role='provider'
        )
        
        # Create provider profile
        self.provider_profile = ProviderProfile.objects.create(
            user=self.provider_user
        )
        
        # Create category and service
        self.category = Category.objects.create(
            name_ru='Музыканты',
            name_en='Musicians',
            slug='musicians'
        )
        
        self.service = Service.objects.create(
            provider=self.provider_profile,
            category=self.category,
            title='Live Music',
            price_amount=50000,
            price_type='event',
            city='Алматы'
        )
        
        # Create event request
        event_date = timezone.now() + timedelta(days=30)
        self.request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            title='Wedding Music',
            city='Алматы',
            event_date=event_date,
            budget_min=40000,
            budget_max=60000,
            status=EventRequest.Status.OFFERS,
            target_provider=self.provider_profile,
            target_service=self.service
        )
        
        # Create offer
        self.offer = Offer.objects.create(
            request=self.request,
            service=self.service,
            provider_profile=self.provider_profile,
            price=50000,
            cover_letter='I can play at your wedding!',
            status=Offer.Status.SENT
        )
        
        # API clients
        self.client_api = APIClient()
        self.client_api.force_authenticate(user=self.client_user)
        
        self.provider_api = APIClient()
        self.provider_api.force_authenticate(user=self.provider_user)
    
    def test_accept_offer_creates_order_with_correct_provider(self):
        """Test that accepting offer creates order with provider_profile set correctly"""
        # Client accepts offer
        response = self.client_api.post(f'/api/v1/offers/{self.offer.id}/accept/')
        self.assertEqual(response.status_code, 200)
        
        # Verify order created
        order = Order.objects.get(offer=self.offer)
        self.assertIsNotNone(order)
        self.assertEqual(order.provider_profile, self.provider_profile)
        self.assertEqual(order.client, self.client_user)
        self.assertEqual(order.price_agreed, self.offer.price)
    
    def test_provider_sees_accepted_order_in_list(self):
        """Test that provider can see order in their order list after client accepts"""
        # Accept offer as client
        self.client_api.post(f'/api/v1/offers/{self.offer.id}/accept/')
        order = Order.objects.get(offer=self.offer)
        
        # Provider fetches their orders
        response = self.provider_api.get('/api/v1/orders/')
        self.assertEqual(response.status_code, 200)
        
        # Parse response (handle pagination)
        if isinstance(response.data, list):
            orders = response.data
        else:
            orders = response.data.get('results', [])
        
        # Verify provider sees the order
        order_ids = [o['id'] for o in orders]
        self.assertIn(order.id, order_ids, 
                     f"Provider should see order {order.id} in their list. Got: {order_ids}")
    
    def test_client_sees_accepted_order_in_list(self):
        """Test that client can see order in their order list after accepting"""
        # Accept offer
        self.client_api.post(f'/api/v1/offers/{self.offer.id}/accept/')
        order = Order.objects.get(offer=self.offer)
        
        # Client fetches their orders
        response = self.client_api.get('/api/v1/orders/')
        self.assertEqual(response.status_code, 200)
        
        # Parse response
        if isinstance(response.data, list):
            orders = response.data
        else:
            orders = response.data.get('results', [])
        
        # Verify client sees the order
        order_ids = [o['id'] for o in orders]
        self.assertIn(order.id, order_ids,
                     f"Client should see order {order.id} in their list. Got: {order_ids}")
    
    def test_provider_can_access_order_detail(self):
        """Test that provider can access order detail page without 403/404"""
        # Accept offer
        self.client_api.post(f'/api/v1/offers/{self.offer.id}/accept/')
        order = Order.objects.get(offer=self.offer)
        
        # Provider accesses order detail
        response = self.provider_api.get(f'/api/v1/orders/{order.id}/')
        self.assertEqual(response.status_code, 200,
                        f"Provider should have access to order {order.id} detail. Got status: {response.status_code}")
        self.assertEqual(response.data['id'], order.id)
    
    def test_client_can_access_order_detail(self):
        """Test that client can access order detail page"""
        # Accept offer
        self.client_api.post(f'/api/v1/offers/{self.offer.id}/accept/')
        order = Order.objects.get(offer=self.offer)
        
        # Client accesses order detail
        response = self.client_api.get(f'/api/v1/orders/{order.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], order.id)
    
    def test_provider_without_profile_sees_no_orders(self):
        """Test that provider without provider_profile sees no orders"""
        # Create provider user without profile
        provider_no_profile = User.objects.create_user(
            email='provider_noprofile@test.com',
            password='Test1234',
            role='provider'
        )
        
        api = APIClient()
        api.force_authenticate(user=provider_no_profile)
        
        response = api.get('/api/v1/orders/')
        self.assertEqual(response.status_code, 200)
        
        if isinstance(response.data, list):
            orders = response.data
        else:
            orders = response.data.get('results', [])
        
        self.assertEqual(len(orders), 0, "Provider without profile should see no orders")
    
    def test_third_party_cannot_see_order(self):
        """Test that unrelated user cannot see order"""
        # Create third user
        third_user = User.objects.create_user(
            email='third@test.com',
            password='Test1234',
            role='client'
        )
        
        # Accept offer
        self.client_api.post(f'/api/v1/offers/{self.offer.id}/accept/')
        order = Order.objects.get(offer=self.offer)
        
        # Third party tries to access
        third_api = APIClient()
        third_api.force_authenticate(user=third_user)
        
        # List should be empty
        response = third_api.get('/api/v1/orders/')
        if isinstance(response.data, list):
            orders = response.data
        else:
            orders = response.data.get('results', [])
        self.assertEqual(len(orders), 0)
        
        # Detail should be 403 or 404
        response = third_api.get(f'/api/v1/orders/{order.id}/')
        self.assertIn(response.status_code, [403, 404])
