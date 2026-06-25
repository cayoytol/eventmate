from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import ProviderProfile
from apps.catalog.models import Category

User = get_user_model()

class ServicePriceSecurityTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name_ru="Тест",
            name_en="Test",
            name_kz="Тест",
            slug="test"
        )
        self.provider_user = User.objects.create_user(
            email="provider_test@test.com",
            password="password123",
            role="provider"
        )
        self.provider_profile = ProviderProfile.objects.create(user=self.provider_user)
        self.client = APIClient()

    def test_negative_service_price_rejected(self):
        self.client.force_authenticate(user=self.provider_user)
        response = self.client.post('/api/v1/services/', {
            'category': self.category.id,
            'title': 'Test Service',
            'description': 'Description',
            'price_type': 'fixed',
            'price_amount': '-500',  # negative price!
            'city': 'Almaty',
            'is_active': True
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('price_amount', response.data)

    def test_positive_service_price_accepted(self):
        self.client.force_authenticate(user=self.provider_user)
        response = self.client.post('/api/v1/services/', {
            'category': self.category.id,
            'title': 'Test Service',
            'description': 'Description',
            'price_type': 'fixed',
            'price_amount': '500.00',  # valid positive price
            'city': 'Almaty',
            'is_active': True
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
