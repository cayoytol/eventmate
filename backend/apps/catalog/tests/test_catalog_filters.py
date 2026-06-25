from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import ProviderProfile
from apps.catalog.models import Service, Category

User = get_user_model()


class CatalogFiltersTest(TestCase):
    def setUp(self):
        # Create categories
        self.category_photo = Category.objects.create(
            name_ru="Фотография",
            name_en="Photography",
            name_kz="Фотография",
            slug="photo"
        )
        self.category_decor = Category.objects.create(
            name_ru="Декор",
            name_en="Decor",
            name_kz="Декор",
            slug="decor"
        )

        # Create Providers
        self.provider_1_user = User.objects.create_user(
            email="provider1@test.com",
            password="password123",
            role="provider"
        )
        self.provider_1_profile = ProviderProfile.objects.create(user=self.provider_1_user)

        self.provider_2_user = User.objects.create_user(
            email="provider2@test.com",
            password="password123",
            role="provider"
        )
        self.provider_2_profile = ProviderProfile.objects.create(user=self.provider_2_user)

        # Create services
        # Service 1: Almaty, photography, 50000, active, provider 1
        self.service_1 = Service.objects.create(
            title="Professional Wedding Photography",
            description="Elite photo session in Almaty city center",
            price_amount="50000.00",
            price_type="fixed",
            city="Almaty",
            category=self.category_photo,
            provider=self.provider_1_profile,
            is_active=True,
            latitude=43.238949,
            longitude=76.889709
        )

        # Service 2: Astana, photography, 120000, active, provider 2
        self.service_2 = Service.objects.create(
            title="Quick Birthday Photoshoot",
            description="Studio and outdoor birthday photo sessions",
            price_amount="120000.00",
            price_type="fixed",
            city="Astana",
            category=self.category_photo,
            provider=self.provider_2_profile,
            is_active=True,
            latitude=51.169392,
            longitude=71.449074
        )

        # Service 3: Almaty, decor, 80000, active, provider 1
        self.service_3 = Service.objects.create(
            title="Premium Floral Decor",
            description="Luxury hall decorations using fresh flowers",
            price_amount="80000.00",
            price_type="fixed",
            city="Almaty",
            category=self.category_decor,
            provider=self.provider_1_profile,
            is_active=True,
            latitude=43.2551,
            longitude=76.9126
        )

        # Service 4: Almaty, photography, 30000, inactive, provider 1
        self.service_4 = Service.objects.create(
            title="Cheap Portrait Session",
            description="Budget friendly headshots in Almaty",
            price_amount="30000.00",
            price_type="fixed",
            city="Almaty",
            category=self.category_photo,
            provider=self.provider_1_profile,
            is_active=False,
            latitude=43.2220,
            longitude=76.8500
        )

        self.client = APIClient()

        # Update created_at to ensure deterministic ordering in tests
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        Service.objects.filter(id=self.service_1.id).update(created_at=now - timedelta(hours=3))
        Service.objects.filter(id=self.service_2.id).update(created_at=now - timedelta(hours=2))
        Service.objects.filter(id=self.service_3.id).update(created_at=now - timedelta(hours=1))
        Service.objects.filter(id=self.service_4.id).update(created_at=now)

    def get_service_ids(self, response_data):
        if isinstance(response_data, list):
            return [item["id"] for item in response_data]
        return [item["id"] for item in response_data.get("results", [])]

    def test_filter_by_city_case_insensitive_substring(self):
        """Should filter services matching city as case-insensitive substring"""
        response = self.client.get("/api/v1/services/", {"city": "almA"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_1.id, ids)
        self.assertIn(self.service_3.id, ids)
        self.assertNotIn(self.service_2.id, ids)

    def test_filter_by_category_id(self):
        """Should filter services matching category_id"""
        response = self.client.get("/api/v1/services/", {"category_id": self.category_decor.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_3.id, ids)
        self.assertNotIn(self.service_1.id, ids)
        self.assertNotIn(self.service_2.id, ids)

    def test_filter_by_category_slug(self):
        """Should filter services matching category_slug"""
        response = self.client.get("/api/v1/services/", {"category_slug": "photo"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_1.id, ids)
        self.assertIn(self.service_2.id, ids)
        self.assertNotIn(self.service_3.id, ids)

    def test_filter_by_price_min(self):
        """Should filter services with price >= price_min"""
        response = self.client.get("/api/v1/services/", {"price_min": "80000.00"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_2.id, ids)
        self.assertIn(self.service_3.id, ids)
        self.assertNotIn(self.service_1.id, ids)

    def test_filter_by_price_max(self):
        """Should filter services with price <= price_max"""
        response = self.client.get("/api/v1/services/", {"price_max": "80000.00"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_1.id, ids)
        self.assertIn(self.service_3.id, ids)
        self.assertNotIn(self.service_2.id, ids)

    def test_filter_by_price_min_and_max(self):
        """Should filter services with price within min and max boundaries"""
        response = self.client.get("/api/v1/services/", {"price_min": "60000.00", "price_max": "100000.00"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_3.id, ids)
        self.assertNotIn(self.service_1.id, ids)
        self.assertNotIn(self.service_2.id, ids)

    def test_active_services_only_for_public_catalog(self):
        """Public list request should never include inactive services"""
        response = self.client.get("/api/v1/services/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertNotIn(self.service_4.id, ids)

    def test_provider_me_works_for_provider_owner(self):
        """Authenticated provider requesting provider=me gets their own active + inactive services"""
        self.client.force_authenticate(user=self.provider_1_user)
        response = self.client.get("/api/v1/services/", {"provider": "me"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_1.id, ids)
        self.assertIn(self.service_3.id, ids)
        self.assertIn(self.service_4.id, ids)
        self.assertNotIn(self.service_2.id, ids)

    def test_numeric_provider_id_works(self):
        """Filter by specific provider ID returns only their active services"""
        response = self.client.get("/api/v1/services/", {"provider": self.provider_1_profile.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_1.id, ids)
        self.assertIn(self.service_3.id, ids)
        self.assertNotIn(self.service_2.id, ids)
        self.assertNotIn(self.service_4.id, ids)

    def test_search_by_title(self):
        """Search query matching title should return matching service"""
        response = self.client.get("/api/v1/services/", {"search": "Wedding"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_1.id, ids)
        self.assertNotIn(self.service_2.id, ids)

    def test_search_by_description(self):
        """Search query matching description should return matching service"""
        response = self.client.get("/api/v1/services/", {"search": "Luxury"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_3.id, ids)
        self.assertNotIn(self.service_1.id, ids)

    def test_search_by_city_in_search_field(self):
        """Search query matching city name should return services in that city"""
        response = self.client.get("/api/v1/services/", {"search": "Astana"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_2.id, ids)
        self.assertNotIn(self.service_1.id, ids)

    def test_ordering_by_price_ascending(self):
        """Ordering by price_amount (ascending) should sort services properly"""
        response = self.client.get("/api/v1/services/", {"ordering": "price_amount"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        # Active services: service_1 (50000), service_3 (80000), service_2 (120000)
        self.assertEqual(ids, [self.service_1.id, self.service_3.id, self.service_2.id])

    def test_ordering_by_price_descending(self):
        """Ordering by -price_amount (descending) should sort services properly"""
        response = self.client.get("/api/v1/services/", {"ordering": "-price_amount"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        # Active services: service_2 (120000), service_3 (80000), service_1 (50000)
        self.assertEqual(ids, [self.service_2.id, self.service_3.id, self.service_1.id])

    def test_ordering_by_created_at_descending(self):
        """Ordering by -created_at (descending) should sort services properly"""
        response = self.client.get("/api/v1/services/", {"ordering": "-created_at"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        # Order of creation: service_1, service_2, service_3. Descending should be: service_3, service_2, service_1
        self.assertEqual(ids, [self.service_3.id, self.service_2.id, self.service_1.id])

    def test_serializer_returns_coordinates(self):
        """Verify ServiceListSerializer returns latitude and longitude coordinates in list view"""
        response = self.client.get("/api/v1/services/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()
        if not isinstance(results, list):
            results = results.get("results", [])
        
        # Verify coordinates of Service 1 are returned
        service1_data = next(item for item in results if item["id"] == self.service_1.id)
        self.assertEqual(service1_data["latitude"], 43.238949)
        self.assertEqual(service1_data["longitude"], 76.889709)


from django.core.cache import cache
from apps.catalog.geo_utils import haversine_distance_m, radius_bounding_box

class CatalogGeoFiltersTest(TestCase):
    def setUp(self):
        cache.clear()
        
        self.category_photo = Category.objects.create(
            name_ru="Фотография", name_en="Photography", name_kz="Фотография", slug="photo"
        )
        self.category_decor = Category.objects.create(
            name_ru="Декор", name_en="Decor", name_kz="Декор", slug="decor"
        )
        
        self.provider_user = User.objects.create_user(
            email="provider@test.com", password="password123", role="provider"
        )
        self.provider_profile = ProviderProfile.objects.create(user=self.provider_user)
        
        # Service A: Almaty center, within 1km (distance ~130m)
        self.service_a = Service.objects.create(
            title="Service A", description="Wedding Photos", price_amount="50000.00",
            price_type="fixed", city="Almaty", category=self.category_photo,
            provider=self.provider_profile, is_active=True,
            latitude=43.238000, longitude=76.889000
        )
        # Service B: Almaty center, outside 1km, within 5km (distance ~1.08km)
        self.service_b = Service.objects.create(
            title="Service B", description="Floral Decor", price_amount="80000.00",
            price_type="fixed", city="Almaty", category=self.category_decor,
            provider=self.provider_profile, is_active=True,
            latitude=43.245000, longitude=76.900000
        )
        # Service C: Outside Almaty bbox, far away
        self.service_c = Service.objects.create(
            title="Service C", description="Studio Photoshoot", price_amount="120000.00",
            price_type="fixed", city="Almaty", category=self.category_photo,
            provider=self.provider_profile, is_active=True,
            latitude=43.500000, longitude=77.200000
        )
        # Service D: Coordinate-less service
        self.service_d = Service.objects.create(
            title="Service D", description="Portrait Session", price_amount="30000.00",
            price_type="fixed", city="Almaty", category=self.category_photo,
            provider=self.provider_profile, is_active=True,
            latitude=None, longitude=None
        )
        
        self.client = APIClient()

    def get_service_ids(self, response_data):
        if isinstance(response_data, list):
            return [item["id"] for item in response_data]
        return [item["id"] for item in response_data.get("results", [])]

    # Bbox Tests
    def test_valid_bbox_returns_inside_services(self):
        # Almaty bbox: min_lng=76.80, min_lat=43.15, max_lng=77.05, max_lat=43.35
        response = self.client.get("/api/v1/services/", {"bbox": "76.80,43.15,77.05,43.35"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_a.id, ids)
        self.assertIn(self.service_b.id, ids)
        self.assertNotIn(self.service_c.id, ids)

    def test_outside_service_excluded_from_bbox(self):
        response = self.client.get("/api/v1/services/", {"bbox": "76.80,43.15,77.05,43.35"})
        ids = self.get_service_ids(response.json())
        self.assertNotIn(self.service_c.id, ids)

    def test_missing_coordinate_service_excluded_from_bbox(self):
        response = self.client.get("/api/v1/services/", {"bbox": "76.80,43.15,77.05,43.35"})
        ids = self.get_service_ids(response.json())
        self.assertNotIn(self.service_d.id, ids)

    def test_category_combines_with_bbox(self):
        response = self.client.get("/api/v1/services/", {
            "bbox": "76.80,43.15,77.05,43.35",
            "category_id": self.category_decor.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_b.id, ids)
        self.assertNotIn(self.service_a.id, ids)

    def test_city_search_combines_with_bbox(self):
        response = self.client.get("/api/v1/services/", {
            "bbox": "76.80,43.15,77.05,43.35",
            "search": "Floral"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_b.id, ids)
        self.assertNotIn(self.service_a.id, ids)

    def test_wrong_value_count_returns_400(self):
        response = self.client.get("/api/v1/services/", {"bbox": "76.80,43.15,77.05"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_numeric_value_returns_400(self):
        response = self.client.get("/api/v1/services/", {"bbox": "76.80,abc,77.05,43.35"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nan_returns_400(self):
        response = self.client.get("/api/v1/services/", {"bbox": "76.80,NaN,77.05,43.35"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_infinity_returns_400(self):
        response = self.client.get("/api/v1/services/", {"bbox": "76.80,43.15,Infinity,43.35"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_latitude_outside_range_returns_400(self):
        response = self.client.get("/api/v1/services/", {"bbox": "76.80,-95.0,77.05,43.35"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_longitude_outside_range_returns_400(self):
        response = self.client.get("/api/v1/services/", {"bbox": "-185.0,43.15,77.05,43.35"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reversed_latitude_range_returns_400(self):
        response = self.client.get("/api/v1/services/", {"bbox": "76.80,43.35,77.05,43.15"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reversed_longitude_range_returns_400(self):
        response = self.client.get("/api/v1/services/", {"bbox": "77.05,43.15,76.80,43.35"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # Radius Tests
    def test_valid_radius_returns_nearby_services(self):
        response = self.client.get("/api/v1/services/", {
            "lat": "43.238949",
            "lng": "76.889709",
            "radius": "1500"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_a.id, ids)
        self.assertIn(self.service_b.id, ids)
        self.assertNotIn(self.service_c.id, ids)

    def test_exact_haversine_excludes_candidate_outside_radius(self):
        response = self.client.get("/api/v1/services/", {
            "lat": "43.238949",
            "lng": "76.889709",
            "radius": "500"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_a.id, ids)
        self.assertNotIn(self.service_b.id, ids)

    def test_default_order_is_nearest_first(self):
        response = self.client.get("/api/v1/services/", {
            "lat": "43.238949",
            "lng": "76.889709",
            "radius": "5000"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertEqual(ids, [self.service_a.id, self.service_b.id])

    def test_equal_distance_results_use_deterministic_pk_tie_break(self):
        service_e = Service.objects.create(
            title="Service E", description="Duplicate Location", price_amount="60000.00",
            price_type="fixed", city="Almaty", category=self.category_photo,
            provider=self.provider_profile, is_active=True,
            latitude=43.238000, longitude=76.889000
        )
        response = self.client.get("/api/v1/services/", {
            "lat": "43.238949",
            "lng": "76.889709",
            "radius": "500"
        })
        ids = self.get_service_ids(response.json())
        a_idx = ids.index(self.service_a.id)
        e_idx = ids.index(service_e.id)
        self.assertTrue(a_idx < e_idx)

    def test_distance_m_has_reasonable_accuracy(self):
        response = self.client.get("/api/v1/services/", {
            "lat": "43.238949",
            "lng": "76.889709",
            "radius": "500"
        })
        results = response.json()
        if not isinstance(results, list):
            results = results.get("results", [])
        
        service_a_data = next(item for item in results if item["id"] == self.service_a.id)
        dist = service_a_data["distance_m"]
        self.assertTrue(110 <= dist <= 150)

    def test_missing_coordinate_service_excluded_from_radius(self):
        response = self.client.get("/api/v1/services/", {
            "lat": "43.238949",
            "lng": "76.889709",
            "radius": "5000"
        })
        ids = self.get_service_ids(response.json())
        self.assertNotIn(self.service_d.id, ids)

    def test_partial_parameters_return_400(self):
        response = self.client.get("/api/v1/services/", {"lat": "43.2", "lng": "76.8"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_strings_return_400(self):
        response = self.client.get("/api/v1/services/", {"lat": "43.2", "lng": "76.8", "radius": "abc"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nan_infinity_return_400(self):
        response = self.client.get("/api/v1/services/", {"lat": "43.2", "lng": "76.8", "radius": "NaN"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_latitude_longitude_returns_400(self):
        response = self.client.get("/api/v1/services/", {"lat": "95.0", "lng": "76.8", "radius": "1000"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_radius_below_100_returns_400(self):
        response = self.client.get("/api/v1/services/", {"lat": "43.2", "lng": "76.8", "radius": "50"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_radius_above_100000_returns_400(self):
        response = self.client.get("/api/v1/services/", {"lat": "43.2", "lng": "76.8", "radius": "150000"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_radius_100_is_accepted(self):
        response = self.client.get("/api/v1/services/", {"lat": "43.2", "lng": "76.8", "radius": "100"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_radius_100000_is_accepted(self):
        response = self.client.get("/api/v1/services/", {"lat": "43.2", "lng": "76.8", "radius": "100000"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_existing_filters_combine_with_radius(self):
        response = self.client.get("/api/v1/services/", {
            "lat": "43.238949",
            "lng": "76.889709",
            "radius": "5000",
            "category_id": self.category_decor.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_b.id, ids)
        self.assertNotIn(self.service_a.id, ids)

    def test_pagination_count_results_correct(self):
        response = self.client.get("/api/v1/services/", {
            "lat": "43.238949",
            "lng": "76.889709",
            "radius": "5000"
        })
        res = response.json()
        self.assertIn("count", res)
        self.assertIn("results", res)
        self.assertEqual(res["count"], 2)

    def test_page_2_works_and_preserves_response_shape(self):
        response = self.client.get("/api/v1/services/", {
            "lat": "43.238949",
            "lng": "76.889709",
            "radius": "5000",
            "page": "2",
            "page_size": "1"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertIn("count", res)
        self.assertIn("results", res)
        self.assertEqual(res["count"], 2)
        self.assertEqual(len(res["results"]), 1)
        self.assertIsNotNone(res["previous"])

    def test_bbox_page_2_works_and_preserves_response_shape(self):
        response = self.client.get("/api/v1/services/", {
            "bbox": "76.80,43.15,77.05,43.35",
            "page": "2",
            "page_size": "1"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertIn("count", res)
        self.assertIn("results", res)
        self.assertEqual(res["count"], 2)
        self.assertEqual(len(res["results"]), 1)
        self.assertIsNotNone(res["previous"])

    def test_explicit_supported_ordering_is_preserved(self):
        response = self.client.get("/api/v1/services/", {
            "lat": "43.238949",
            "lng": "76.889709",
            "radius": "5000",
            "ordering": "-price_amount"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertEqual(ids, [self.service_b.id, self.service_a.id])

    # Combinations & Formatting
    def test_bbox_plus_full_radius_returns_400(self):
        response = self.client.get("/api/v1/services/", {
            "bbox": "76,43,77,44", "lat": "43.2", "lng": "76.8", "radius": "1000"
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bbox_plus_only_lat_returns_400(self):
        response = self.client.get("/api/v1/services/", {
            "bbox": "76,43,77,44", "lat": "43.2"
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_geo_parameters_preserves_ordinary_listing(self):
        response = self.client.get("/api/v1/services/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self.get_service_ids(response.json())
        self.assertIn(self.service_d.id, ids)

    def test_bbox_response_omits_distance_m(self):
        response = self.client.get("/api/v1/services/", {"bbox": "76.80,43.15,77.05,43.35"})
        res = response.json()
        results = res.get("results", [])
        for r in results:
            self.assertNotIn("distance_m", r)

    def test_normal_response_omits_distance_m(self):
        response = self.client.get("/api/v1/services/")
        res = response.json()
        results = res.get("results", [])
        for r in results:
            self.assertNotIn("distance_m", r)

    def test_radius_response_includes_distance_m(self):
        response = self.client.get("/api/v1/services/", {
            "lat": "43.238949",
            "lng": "76.889709",
            "radius": "5000"
        })
        res = response.json()
        results = res.get("results", [])
        for r in results:
            self.assertIn("distance_m", r)

    def test_invalid_legacy_coordinate_values_do_not_cause_500(self):
        Service.objects.create(
            title="Service Invalid Coord", description="Description", price_amount="50000.00",
            price_type="fixed", city="Almaty", category=self.category_photo,
            provider=self.provider_profile, is_active=True,
            latitude=150.0, longitude=250.0
        )
        response = self.client.get("/api/v1/services/", {
            "lat": "43.238949",
            "lng": "76.889709",
            "radius": "5000"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_coordinate_index_exists_in_model_metadata(self):
        from django.db import connection
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, Service._meta.db_table)
            lat_lng_indexes = [
                name for name, val in constraints.items()
                if val.get("index") and "latitude" in val.get("columns") and "longitude" in val.get("columns")
            ]
            self.assertTrue(len(lat_lng_indexes) > 0)

    # Math Utility Tests
    def test_haversine_same_point_is_zero(self):
        self.assertEqual(haversine_distance_m(43.2, 76.8, 43.2, 76.8), 0.0)

    def test_known_coordinate_pair_distance(self):
        dist = haversine_distance_m(43.238949, 76.889709, 43.2551, 76.9126)
        self.assertTrue(2500 <= dist <= 2600)

    def test_pole_safe_bounding_box(self):
        min_lng, min_lat, max_lng, max_lat = radius_bounding_box(90.0, 0.0, 5000.0)
        self.assertEqual(min_lng, -180.0)
        self.assertEqual(max_lng, 180.0)
        self.assertEqual(max_lat, 90.0)

    def test_longitude_bounds_clamped(self):
        min_lng, min_lat, max_lng, max_lat = radius_bounding_box(43.2, 179.9, 20000.0)
        self.assertTrue(min_lng >= -180.0)
        self.assertTrue(max_lng <= 180.0)

    def test_latitude_bounds_clamped(self):
        min_lng, min_lat, max_lng, max_lat = radius_bounding_box(89.9, 0.0, 20000.0)
        self.assertTrue(min_lat >= -90.0)
        self.assertTrue(max_lat <= 90.0)

