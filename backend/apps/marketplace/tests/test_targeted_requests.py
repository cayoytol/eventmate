from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, ProviderProfile
from apps.catalog.models import Category, Service
from apps.marketplace.models import EventRequest
from django.utils import timezone
from datetime import timedelta


class TargetedRequestsTest(TestCase):
    """Test targeted contact flow (Stage A1)"""
    
    def setUp(self):
        self.client_api = APIClient()
        
        # Create category
        self.category = Category.objects.create(
            name_ru="Фотография",
            name_en="Photography",
            name_kz="Фотосурет",
            slug="photography"
        )
        
        # Create client user
        self.client_user = User.objects.create_user(
            email="client@test.com",
            password="test123",
            role="client"
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
        self.service_a = Service.objects.create(
            provider=self.provider_a_profile,
            category=self.category,
            title="Professional Photography",
            description="Wedding photography",
            price_amount=50000,
            price_type='fixed',
            city="Almaty"
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
        self.service_b = Service.objects.create(
            provider=self.provider_b_profile,
            category=self.category,
            title="Budget Photography",
            description="Event photography",
            price_amount=30000,
            price_type='fixed',
            city="Almaty"
        )
    
    def _get_request_ids(self, response):
        """Helper to extract request IDs from paginated or non-paginated response"""
        if isinstance(response.data, dict) and 'results' in response.data:
            return [r['id'] for r in response.data['results']]
        return [r['id'] for r in response.data]
    
    def test_fk_type_consistency(self):
        """Ensure target_provider FK type matches Service.provider FK type"""
        # Create targeted request
        request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            target_provider=self.service_a.provider,
            target_service=self.service_a,
            city="Almaty",
            event_date=timezone.now() + timedelta(days=30),
            description="Need photographer"
        )
        
        # Both should be ProviderProfile instances
        self.assertIsInstance(self.service_a.provider, ProviderProfile)
        self.assertIsInstance(request.target_provider, ProviderProfile)
        self.assertEqual(self.service_a.provider, request.target_provider)
    
    def test_create_targeted_request_via_api(self):
        """Client creates targeted request using target_service_id"""
        self.client_api.force_authenticate(user=self.client_user)
        
        payload = {
            "target_service_id": self.service_a.id,
            "description": "Need photographer for wedding",
            "event_date": (timezone.now() + timedelta(days=30)).isoformat(),
            "city": "Almaty",
            "budget_min": 40000,
            "budget_max": 60000
        }
        
        response = self.client_api.post('/api/v1/requests/', payload)
        
        # Debug: print error if not 201
        if response.status_code != status.HTTP_201_CREATED:
            print(f"\n❌ Status: {response.status_code}")
            print(f"Response data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify auto-filled fields
        request = EventRequest.objects.get(id=response.data['id'])
        self.assertEqual(request.target_provider, self.provider_a_profile)
        self.assertEqual(request.target_service, self.service_a)
        self.assertEqual(request.category, self.category)
    
    def test_targeted_request_visible_only_to_target_provider(self):
        """Targeted request should ONLY be visible to target provider"""
        # Create targeted request to Provider A
        request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            target_provider=self.provider_a_profile,
            target_service=self.service_a,
            city="Almaty",
            event_date=timezone.now() + timedelta(days=30),
            description="Need photographer",
            status=EventRequest.Status.OFFERS
        )
        
        # Provider A should see it
        self.client_api.force_authenticate(user=self.provider_a_user)
        response = self.client_api.get('/api/v1/requests/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        request_ids = self._get_request_ids(response)
        self.assertIn(request.id, request_ids)
        
        # Provider B should NOT see it
        self.client_api.force_authenticate(user=self.provider_b_user)
        response = self.client_api.get('/api/v1/requests/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        request_ids = self._get_request_ids(response)
        self.assertNotIn(request.id, request_ids)
    
    def test_general_request_visible_to_all_providers_in_category(self):
        """General request (no target_provider) visible to all providers in category"""
        # Create general request
        request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            city="Almaty",
            event_date=timezone.now() + timedelta(days=30),
            description="Need photographer",
            status=EventRequest.Status.OFFERS
        )
        
        # Both Provider A and B should see it
        self.client_api.force_authenticate(user=self.provider_a_user)
        response_a = self.client_api.get('/api/v1/requests/')
        request_ids_a = self._get_request_ids(response_a)
        
        self.client_api.force_authenticate(user=self.provider_b_user)
        response_b = self.client_api.get('/api/v1/requests/')
        request_ids_b = self._get_request_ids(response_b)
        
        self.assertIn(request.id, request_ids_a)
        self.assertIn(request.id, request_ids_b)
    
    def test_provider_doesnt_see_requests_from_other_categories(self):
        """Provider should NOT see requests from categories they don't service"""
        # Create different category
        other_category = Category.objects.create(
            name_ru="Музыка",
            name_en="Music",
            name_kz="Музыка",
            slug="music"
        )
        
        # Create request in other category
        request = EventRequest.objects.create(
            client=self.client_user,
            category=other_category,
            city="Almaty",
            event_date=timezone.now() + timedelta(days=30),
            description="Need DJ",
            status=EventRequest.Status.OFFERS
        )
        
        # Provider A (photography) should NOT see it
        self.client_api.force_authenticate(user=self.provider_a_user)
        response = self.client_api.get('/api/v1/requests/')
        
        request_ids = self._get_request_ids(response)
        self.assertNotIn(request.id, request_ids)
    
    def test_client_sees_only_own_requests(self):
        """Client should only see their own requests"""
        # Create request by this client
        my_request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            city="Almaty",
            event_date=timezone.now() + timedelta(days=30),
            description="My request"
        )
        
        # Create request by another client
        other_client = User.objects.create_user(
            email="other_client@test.com",
            password="test123",
            role="client"
        )
        other_request = EventRequest.objects.create(
            client=other_client,
            category=self.category,
            city="Almaty",
            event_date=timezone.now() + timedelta(days=30),
            description="Other request"
        )
        
        # Authenticate as first client
        self.client_api.force_authenticate(user=self.client_user)
        response = self.client_api.get('/api/v1/requests/')
        
        request_ids = self._get_request_ids(response)
        
        self.assertIn(my_request.id, request_ids)
        self.assertNotIn(other_request.id, request_ids)

    def test_request_creation_permissions(self):
        """Test that client can create request, but provider and guest cannot"""
        payload = {
            "category": self.category.id,
            "description": "Need photographer for wedding",
            "event_date": (timezone.now() + timedelta(days=30)).isoformat(),
            "city": "Almaty",
            "budget_min": 40000,
            "budget_max": 60000,
            "title": "Wedding photography request"
        }

        # 1. Guest (unauthenticated) cannot create request (401 Unauthorized)
        self.client_api.logout()
        response = self.client_api.post('/api/v1/requests/', payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. Provider cannot create request (403 Forbidden)
        self.client_api.force_authenticate(user=self.provider_a_user)
        response = self.client_api.post('/api/v1/requests/', payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Client can create request (201 Created)
        self.client_api.force_authenticate(user=self.client_user)
        response = self.client_api.post('/api/v1/requests/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

