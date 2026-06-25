"""
Test to verify Offer serializer includes provider object with rating_avg
to prevent frontend crashes from undefined provider properties.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.accounts.models import ProviderProfile
from apps.catalog.models import Category, Service
from apps.marketplace.models import EventRequest, Offer
from decimal import Decimal

User = get_user_model()


class OfferProviderSerializationTest(TestCase):
    """Test that offers always include provider object with rating_avg"""
    
    def setUp(self):
        # Create client user
        self.client_user = User.objects.create_user(
            email='client@test.com',
            username='client_user',
            password='testpass123',
            role='client'
        )
        
        # Create provider user and profile
        self.provider_user = User.objects.create_user(
            email='provider@test.com',
            username='provider_user',
            password='testpass123',
            role='provider'
        )
        self.provider_profile = ProviderProfile.objects.create(
            user=self.provider_user,
            bio='Test Provider Bio',
            rating_avg=Decimal('4.5'),
            reviews_count=10
        )
        
        # Create category and service
        self.category = Category.objects.create(
            name_ru='Тестовая категория',
            name_en='Test Category'
        )
        self.service = Service.objects.create(
            provider=self.provider_profile,
            title='Test Service',
            description='Test Description',
            category=self.category,
            price_amount=Decimal('100.00'),
            price_type='fixed',
            city='Almaty',
            is_active=True
        )
        
        from django.utils import timezone
        from datetime import timedelta
        # Create request
        self.request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            title='Test Event',
            city='Test City',
            budget_min=Decimal('100.00'),
            budget_max=Decimal('500.00'),
            status='open',
            event_date=timezone.now() + timedelta(days=5)
        )
        
        self.api_client = APIClient()
    
    def test_offer_includes_provider_with_rating(self):
        """Test that offer includes full provider object with rating_avg"""
        # Create offer
        offer = Offer.objects.create(
            request=self.request,
            service=self.service,
            provider_profile=self.provider_profile,
            price=Decimal('300.00'),
            cover_letter='Test offer'
        )
        
        # Login as client
        self.api_client.force_authenticate(user=self.client_user)
        
        # Get request detail offers
        response = self.api_client.get(f'/api/v1/requests/{self.request.id}/offers/')
        
        self.assertEqual(response.status_code, 200)
        
        # Check that response has offers
        # Note: The response structure may vary, adjust based on actual API
        data = response.json()
        
        # Try to find offers in response
        offers = None
        if 'offers' in data:
            offers = data['offers']
        elif isinstance(data, list):
            # If endpoint returns list of offers directly
            offers = data
        
        # Verify we got offers
        self.assertIsNotNone(offers, "Could not find offers in API response")
        self.assertGreater(len(offers), 0, "No offers returned")
        
        # Check first offer
        offer_data = offers[0]
        
        # CRITICAL: provider must be an object, not None
        self.assertIn('provider', offer_data, 
                     "Offer must include 'provider' field")
        self.assertIsNotNone(offer_data['provider'],
                            "Offer provider must not be None")
        
        # Check provider has expected fields
        provider = offer_data['provider']
        self.assertIn('id', provider)
        self.assertIn('rating_avg', provider)
        self.assertIn('user', provider)
        
        # Check rating_avg is correct type
        self.assertIsNotNone(provider['rating_avg'])
        self.assertEqual(float(provider['rating_avg']), 4.5)
        
        # Check user is nested
        self.assertIn('email', provider['user'])
        self.assertEqual(provider['user']['email'], 'provider@test.com')
    
    def test_offer_provider_without_rating(self):
        """Test that offer handles provider with no rating gracefully"""
        # Create provider without rating
        provider2 = ProviderProfile.objects.create(
            user=User.objects.create_user(
                email='provider2@test.com',
                username='provider2',
                password='testpass123',
                role='provider'
            ),
            bio='Provider without rating',
            rating_avg=Decimal('0.0'),  # Cannot be NULL in model
            reviews_count=0
        )
        
        service2 = Service.objects.create(
            provider=provider2,
            title='Service 2',
            description='Test',
            category=self.category,
            price_amount=Decimal('50.00'),
            price_type='fixed',
            city='Almaty',
            is_active=True
        )
        
        offer2 = Offer.objects.create(
            request=self.request,
            service=service2,
            provider_profile=provider2,
            price=Decimal('150.00'),
            cover_letter='Test offer 2'
        )
        
        # Login and fetch
        self.api_client.force_authenticate(user=self.client_user)
        response = self.api_client.get(f'/api/v1/requests/{self.request.id}/offers/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Find offer with provider2
        offers = data if isinstance(data, list) else data.get('offers', [])
        offer_data = None
        for o in offers:
            if o['id'] == offer2.id:
                offer_data = o
                break
        
        self.assertIsNotNone(offer_data)
        self.assertIn('provider', offer_data)
        self.assertIsNotNone(offer_data['provider'])
        
        # rating_avg can be null, but provider object must exist
        provider = offer_data['provider']
        self.assertIn('rating_avg', provider)
        self.assertEqual(float(provider['rating_avg']), 0.0)
