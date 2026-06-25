import json
import logging
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import ProviderProfile
from apps.catalog.models import Category, Service
from apps.catalog.geocoding import geocode_address, reverse_geocode, get_geocode_cache_key

User = get_user_model()

@override_settings(
    DGIS_GEOCODING_ENABLED=True,
    DGIS_API_KEY="test_dgis_key_12345",
    DGIS_API_URL="https://catalog.api.2gis.com/3.0/items/geocode",
    DGIS_GEOCODING_CACHE_SECONDS=60,
    DGIS_GEOCODING_MAX_QUERY_LENGTH=200,
    DGIS_GEOCODING_RESULT_LIMIT=5,
    DGIS_TIMEOUT_SECONDS=5
)
class GeocodingAndCoordinateTest(TestCase):
    def setUp(self):
        cache.clear()
        
        self.category = Category.objects.create(
            name_ru="Тестовая Категория",
            name_en="Test Category",
            name_kz="Тест Санат",
            slug="test-category"
        )
        
        self.provider_user = User.objects.create_user(
            email="provider@test.com",
            password="password123",
            role="provider"
        )
        self.provider_profile = ProviderProfile.objects.create(user=self.provider_user)
        
        self.client_user = User.objects.create_user(
            email="client@test.com",
            password="password123",
            role="client"
        )
        
        self.staff_user = User.objects.create_user(
            email="staff@test.com",
            password="password123",
            role="client",
            is_staff=True
        )
        
        # Create a service with coordinates
        self.service = Service.objects.create(
            provider=self.provider_profile,
            category=self.category,
            title="Service with Location",
            description="Service Description",
            price_type="fixed",
            price_amount="1500.00",
            city="Almaty",
            address="Al-Farabi 77",
            latitude=43.22,
            longitude=76.92
        )
        
        # Create a service without coordinates
        self.service_no_coords = Service.objects.create(
            provider=self.provider_profile,
            category=self.category,
            title="Service without Location",
            description="Service Description",
            price_type="fixed",
            price_amount="2500.00",
            city="Astana",
            address=""
        )
        
        self.api_client = APIClient()

    def test_patch_without_location_fields_preserves_coordinates(self):
        self.api_client.force_authenticate(user=self.provider_user)
        response = self.api_client.patch(
            f'/api/v1/services/{self.service.id}/',
            {'title': 'Updated Title Only'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.service.refresh_from_db()
        self.assertEqual(self.service.title, 'Updated Title Only')
        self.assertEqual(self.service.latitude, 43.22)
        self.assertEqual(self.service.longitude, 76.92)

    def test_patch_with_both_coordinates_null_clears_location(self):
        self.api_client.force_authenticate(user=self.provider_user)
        response = self.api_client.patch(
            f'/api/v1/services/{self.service.id}/',
            {
                'latitude': None,
                'longitude': None
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.service.refresh_from_db()
        self.assertIsNone(self.service.latitude)
        self.assertIsNone(self.service.longitude)

    def test_patch_with_one_coordinate_null_rejected(self):
        self.api_client.force_authenticate(user=self.provider_user)
        
        # Case A: latitude null, longitude value
        response = self.api_client.patch(
            f'/api/v1/services/{self.service.id}/',
            {
                'latitude': None,
                'longitude': 76.92
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Case B: latitude value, longitude null
        response = self.api_client.patch(
            f'/api/v1/services/{self.service.id}/',
            {
                'latitude': 43.22,
                'longitude': None
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_service_update_serializer_accepts_valid_address_and_coordinate_pair(self):
        self.api_client.force_authenticate(user=self.provider_user)
        response = self.api_client.patch(
            f'/api/v1/services/{self.service.id}/',
            {
                'address': 'Dostyk 100',
                'city': 'Almaty',
                'latitude': 43.235,
                'longitude': 76.889
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.service.refresh_from_db()
        self.assertEqual(self.service.address, 'Dostyk 100')
        self.assertEqual(self.service.city, 'Almaty')
        self.assertEqual(self.service.latitude, 43.235)
        self.assertEqual(self.service.longitude, 76.889)

    @patch('urllib.request.urlopen')
    def test_geocoder_sends_city_as_part_of_q(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "result": {
                "items": [
                    {
                        "id": "123",
                        "name": "Абая 10",
                        "full_name": "Алматы, Абая 10",
                        "point": {"lat": 43.2, "lon": 76.8},
                        "adm_div": {"city": {"name": "Алматы"}}
                    }
                ]
            }
        }).encode('utf-8')
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        geocode_address(query="Абая 10", locale="ru", city="Алматы")
        
        self.assertTrue(mock_urlopen.called)
        called_req = mock_urlopen.call_args[0][0]
        called_url = called_req.full_url
        
        self.assertIn("q=%D0%90%D0%BB%D0%BC%D0%B0%D1%82%D1%8B%2C+%D0%90%D0%B1%D0%B0%D1%8F+10", called_url)
        self.assertNotIn("city=", called_url)

    @patch('urllib.request.urlopen')
    def test_required_fields_parameter_is_sent(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"result": {"items": []}}).encode('utf-8')
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        geocode_address(query="Абая 10", locale="ru")
        called_req = mock_urlopen.call_args[0][0]
        called_url = called_req.full_url
        
        self.assertIn("fields=items.point%2Citems.address%2Citems.full_address_name%2Citems.adm_div", called_url)

    @patch('urllib.request.urlopen')
    def test_english_locale_is_omitted(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"result": {"items": []}}).encode('utf-8')
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        geocode_address(query="Abay 10", locale="en")
        called_req = mock_urlopen.call_args[0][0]
        called_url = called_req.full_url
        
        self.assertNotIn("locale=", called_url)

    @patch('urllib.request.urlopen')
    def test_full_external_url_api_key_not_in_logs_on_failure(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://catalog.api.2gis.com/3.0/items/geocode?key=secret_key",
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=None
        )

        with self.assertLogs('apps.catalog.geocoding', level='ERROR') as log_capture:
            geocode_address(query="Абая 10", locale="ru")
            
        logs_text = "".join(log_capture.output)
        self.assertNotIn("secret_key", logs_text)
        self.assertNotIn("test_dgis_key_12345", logs_text)
        self.assertNotIn("https://catalog.api.2gis.com", logs_text)

    @patch('urllib.request.urlopen')
    def test_timeout_and_malformed_response_not_cached(self, mock_urlopen):
        import urllib.error
        
        # 1. Timeout failure (URLError)
        mock_urlopen.side_effect = urllib.error.URLError("timeout")
        geocode_address(query="Timeout Test", locale="ru")
        
        key1 = get_geocode_cache_key("Timeout Test", "ru")
        self.assertIsNone(cache.get(key1))
        
        # 2. Malformed JSON response
        mock_urlopen.side_effect = None
        mock_response = MagicMock()
        mock_response.read.return_value = b"invalid json response"
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        geocode_address(query="Malformed Test", locale="ru")
        
        key2 = get_geocode_cache_key("Malformed Test", "ru")
        self.assertIsNone(cache.get(key2))

    @patch('urllib.request.urlopen')
    def test_cache_key_separates_ru_kz_en_requests(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "result": {
                "items": [
                    {
                        "id": "1",
                        "name": "Абая 10",
                        "full_name": "Абая 10",
                        "point": {"lat": 43.2, "lon": 76.8},
                        "adm_div": {"city": {"name": "Алматы"}}
                    }
                ]
            }
        }).encode('utf-8')
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Call with ru
        geocode_address(query="Абая 10", locale="ru")
        # Call with kz
        geocode_address(query="Абая 10", locale="kz")
        # Call with en
        geocode_address(query="Абая 10", locale="en")
        
        # Total urlopen calls should be 3 because cache keys are separate
        self.assertEqual(mock_urlopen.call_count, 3)

    def test_permissions_client_and_anonymous_blocked_staff_and_provider_allowed(self):
        # 1. Anonymous user (blocked)
        response = self.api_client.post('/api/v1/geo/geocode/', {'query': 'Абая 10'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        response = self.api_client.post('/api/v1/geo/reverse-geocode/', {'latitude': 43.2, 'longitude': 76.8}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # 2. Client user (blocked)
        self.api_client.force_authenticate(user=self.client_user)
        response = self.api_client.post('/api/v1/geo/geocode/', {'query': 'Абая 10'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # 3. Provider user (allowed)
        self.api_client.force_authenticate(user=self.provider_user)
        response = self.api_client.post('/api/v1/geo/geocode/', {'query': 'Абая 10'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 4. Staff user (allowed)
        self.api_client.force_authenticate(user=self.staff_user)
        response = self.api_client.post('/api/v1/geo/geocode/', {'query': 'Абая 10'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
