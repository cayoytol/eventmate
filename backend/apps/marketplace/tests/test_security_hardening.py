from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, ProviderProfile
from apps.catalog.models import Category, Service
from apps.marketplace.models import EventRequest
from django.utils import timezone
from datetime import timedelta

class MarketplaceSecurityHardeningTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name_ru="Тест",
            name_en="Test",
            name_kz="Тест",
            slug="test"
        )
        
        self.client_user = User.objects.create_user(
            email="client@test.com",
            password="password123",
            role="client"
        )
        
        self.provider_user = User.objects.create_user(
            email="provider@test.com",
            password="password123",
            role="provider"
        )
        self.provider_profile = ProviderProfile.objects.create(user=self.provider_user)
        
        self.service = Service.objects.create(
            provider=self.provider_profile,
            category=self.category,
            title="Service Title",
            description="Description",
            price_amount=5000,
            price_type='fixed',
            city="Almaty"
        )
        
        self.client_api = APIClient()

    def test_negative_budget_min_rejected(self):
        self.client_api.force_authenticate(user=self.client_user)
        response = self.client_api.post('/api/v1/requests/', {
            'category': self.category.id,
            'title': 'Request Title',
            'city': 'Almaty',
            'event_date': (timezone.now() + timedelta(days=5)).isoformat(),
            'budget_min': '-100',
            'budget_max': '500',
            'description': 'Description'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('budget_min', response.data)

    def test_negative_budget_max_rejected(self):
        self.client_api.force_authenticate(user=self.client_user)
        response = self.client_api.post('/api/v1/requests/', {
            'category': self.category.id,
            'title': 'Request Title',
            'city': 'Almaty',
            'event_date': (timezone.now() + timedelta(days=5)).isoformat(),
            'budget_min': '100',
            'budget_max': '-500',
            'description': 'Description'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('budget_max', response.data)

    def test_budget_range_invalid_rejected(self):
        self.client_api.force_authenticate(user=self.client_user)
        response = self.client_api.post('/api/v1/requests/', {
            'category': self.category.id,
            'title': 'Request Title',
            'city': 'Almaty',
            'event_date': (timezone.now() + timedelta(days=5)).isoformat(),
            'budget_min': '500',
            'budget_max': '100',  # min > max
            'description': 'Description'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('budget_max', response.data)

    def test_valid_request_budget_passes(self):
        self.client_api.force_authenticate(user=self.client_user)
        response = self.client_api.post('/api/v1/requests/', {
            'category': self.category.id,
            'title': 'Request Title',
            'city': 'Almaty',
            'event_date': (timezone.now() + timedelta(days=5)).isoformat(),
            'budget_min': '100',
            'budget_max': '500',
            'description': 'Description'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_negative_offer_price_rejected(self):
        req = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            title='Req',
            city='Almaty',
            event_date=timezone.now() + timedelta(days=5),
            description='Test',
            status=EventRequest.Status.OFFERS
        )
        
        self.client_api.force_authenticate(user=self.provider_user)
        response = self.client_api.post('/api/v1/offers/', {
            'request': req.id,
            'service': self.service.id,
            'price': '-500',  # negative offer price
            'cover_letter': 'Hello'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('price', response.data)

    def test_positive_offer_price_accepted(self):
        req = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            title='Req',
            city='Almaty',
            event_date=timezone.now() + timedelta(days=5),
            description='Test',
            status=EventRequest.Status.OFFERS
        )
        
        # Seed provider subscription to allow offer creation
        from apps.billing.models import Plan, Subscription
        plan = Plan.objects.create(
            name_ru="Тест",
            price=0,
            duration_days=30,
            limits_json={"max_services": 10, "offers_per_month": 10},
            is_active=True
        )
        Subscription.objects.create(
            provider_profile=self.provider_profile,
            plan=plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            status='active'
        )

        self.client_api.force_authenticate(user=self.provider_user)
        response = self.client_api.post('/api/v1/offers/', {
            'request': req.id,
            'service': self.service.id,
            'price': '500.00',  # positive price
            'cover_letter': 'Hello'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
