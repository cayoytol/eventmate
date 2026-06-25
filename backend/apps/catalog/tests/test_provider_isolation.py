"""
Test provider isolation - ensure ?provider=me returns only authenticated user's services
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import ProviderProfile
from apps.catalog.models import Service, Category

User = get_user_model()


class ProviderServicesIsolationTest(TestCase):
    """Regression test: provider A must not see provider B's services"""

    def setUp(self):
        # Create category
        self.category = Category.objects.create(
            name_ru="Тест",
            name_en="Test",
            name_kz="Тест",
            slug="test"
        )

        # Create Provider A
        self.provider_a_user = User.objects.create_user(
            email="provider_a@test.com",
            password="test123",
            role="provider"
        )
        self.provider_a_profile = ProviderProfile.objects.create(
            user=self.provider_a_user
        )

        # Create Provider B
        self.provider_b_user = User.objects.create_user(
            email="provider_b@test.com",
            password="test123",
            role="provider"
        )
        self.provider_b_profile = ProviderProfile.objects.create(
            user=self.provider_b_user
        )

        # Create service for Provider A
        self.service_a = Service.objects.create(
            title="Service A1",
            description="Provider A's service",
            price_amount="1000.00",
            price_type="fixed",
            city="Almaty",
            category=self.category,
            provider=self.provider_a_profile,
            is_active=True
        )

        # Create service for Provider B
        self.service_b = Service.objects.create(
            title="Service B1",
            description="Provider B's service",
            price_amount="2000.00",
            price_type="fixed",
            city="Astana",
            category=self.category,
            provider=self.provider_b_profile,
            is_active=True
        )

        self.client = APIClient()

    def test_provider_b_sees_only_own_services(self):
        """Provider B with ?provider=me should see ONLY B1, not A1"""
        # Authenticate as Provider B
        self.client.force_authenticate(user=self.provider_b_user)

        # Request "my services"
        response = self.client.get('/api/v1/services/', {'provider': 'me'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Handle both array and paginated responses
        data = response.json()
        if isinstance(data, list):
            services = data
        else:
            services = data.get('results', [])

        # MUST return exactly 1 service (B1)
        self.assertEqual(len(services), 1, 
                        "Provider B should see exactly 1 service (their own)")

        # Verify it's B1, not A1
        self.assertEqual(services[0]['id'], self.service_b.id)
        self.assertEqual(services[0]['title'], "Service B1")

        # Ensure A1 is NOT in the response
        service_ids = [s['id'] for s in services]
        self.assertNotIn(self.service_a.id, service_ids,
                        "Provider B should NOT see Provider A's services")

    def test_provider_a_sees_only_own_services(self):
        """Provider A with ?provider=me should see ONLY A1, not B1"""
        # Authenticate as Provider A
        self.client.force_authenticate(user=self.provider_a_user)

        # Request "my services"
        response = self.client.get('/api/v1/services/', {'provider': 'me'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        if isinstance(data, list):
            services = data
        else:
            services = data.get('results', [])

        # MUST return exactly 1 service (A1)
        self.assertEqual(len(services), 1)
        self.assertEqual(services[0]['id'], self.service_a.id)
        self.assertEqual(services[0]['title'], "Service A1")

        # Ensure B1 is NOT in the response
        service_ids = [s['id'] for s in services]
        self.assertNotIn(self.service_b.id, service_ids)

    def test_unauthenticated_provider_me_returns_empty(self):
        """Unauthenticated request with ?provider=me should return empty"""
        # No authentication
        response = self.client.get('/api/v1/services/', {'provider': 'me'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        if isinstance(data, list):
            services = data
        else:
            services = data.get('results', [])

        # Must be empty
        self.assertEqual(len(services), 0,
                        "Unauthenticated users should have no 'my services'")

    def test_client_role_provider_me_returns_empty(self):
        """Non-provider users with ?provider=me should return empty"""
        # Create client user
        client_user = User.objects.create_user(
            email="client@test.com",
            password="test123",
            role="client"
        )
        self.client.force_authenticate(user=client_user)

        response = self.client.get('/api/v1/services/', {'provider': 'me'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        if isinstance(data, list):
            services = data
        else:
            services = data.get('results', [])

        # Clients don't have services
        self.assertEqual(len(services), 0)

    def test_public_catalog_shows_only_active_services(self):
        """Public catalog (no ?provider=me) should show only active services from all providers"""
        # Create another service for Provider A (inactive)
        service_a_inactive = Service.objects.create(
            title="Service A2 (inactive)",
            description="Provider A's inactive service",
            price_amount="500.00",
            price_type="fixed",
            city="Almaty",
            category=self.category,
            provider=self.provider_a_profile,
            is_active=False  # Inactive
        )

        # Unauthenticated request (public catalog)
        response = self.client.get('/api/v1/services/')  # No provider=me

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        if isinstance(data, list):
            services = data
        else:
            services = data.get('results', [])

        # Should return 2 active services (A1 and B1)
        self.assertEqual(len(services), 2)

        service_ids = [s['id'] for s in services]
        
        # A1 (active) should be visible
        self.assertIn(self.service_a.id, service_ids)
        
        # B1 (active) should be visible
        self.assertIn(self.service_b.id, service_ids)
        
        # A2 (inactive) should NOT be visible
        self.assertNotIn(service_a_inactive.id, service_ids,
                        "Inactive services should not appear in public catalog")
        
    def test_provider_sees_all_active_plus_own_inactive(self):
        """Provider in public catalog (no ?provider=me) sees all active + own inactive"""
        # Create inactive service for Provider A
        service_a_inactive = Service.objects.create(
            title="Service A2 (inactive)",
            description="Provider A's inactive service",
            price_amount="500.00",
            price_type="fixed",
            city="Almaty",
            category=self.category,
            provider=self.provider_a_profile,
            is_active=False
        )

        # Authenticate as Provider A
        self.client.force_authenticate(user=self.provider_a_user)

        # Request catalog (NO provider=me parameter)
        response = self.client.get('/api/v1/services/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        if isinstance(data, list):
            services = data
        else:
            services = data.get('results', [])

        service_ids = [s['id'] for s in services]

        # Should see 3 services total
        self.assertEqual(len(services), 3)
        
        # A1 (active, own) ✅
        self.assertIn(self.service_a.id, service_ids)
        
        # A2 (inactive, own) ✅ - Provider sees own inactive
        self.assertIn(service_a_inactive.id, service_ids)
        
        # B1 (active, other) ✅ - Provider sees other active
        self.assertIn(self.service_b.id, service_ids)

