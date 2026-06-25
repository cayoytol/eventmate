from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from apps.accounts.models import Availability, ProviderProfile
from apps.marketplace.models import Order, Offer, EventRequest
from apps.catalog.models import Service, Category

User = get_user_model()

class AvailabilityTests(APITestCase):
    def setUp(self):
        # Create Provider
        self.provider_user = User.objects.create_user(
            email='provider@example.com', 
            password='password123', 
            role='provider'
        )
        self.provider_profile = ProviderProfile.objects.create(user=self.provider_user)
        self.client.force_authenticate(user=self.provider_user)
        
        # Create Client
        self.client_user = User.objects.create_user(
            email='client@example.com', 
            password='password123', 
            role='client'
        )
        
        # Create Category
        self.category = Category.objects.create(
            name_ru='Test Category',
            slug='test-category'
        )
        
        # Create Service
        self.service = Service.objects.create(
            provider=self.provider_profile,
            category=self.category,
            title='Test Service',
            price_amount=100,
            description='Test Service Description',
            city='Almaty',
            duration_minutes=90
        )

    def test_availability_crud(self):
        """
        Test Create, Read, Delete for Availability slots (Time-based).
        """
        # 1. Create blocked slot
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        start_at = now + timedelta(days=1, hours=10) # Tomorrow 10:00
        end_at = start_at + timedelta(hours=2)       # Tomorrow 12:00
        
        data = {
            'start_at': start_at.isoformat(),
            'end_at': end_at.isoformat()
        }
        res = self.client.post('/api/v1/availability/', data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        slot_id = res.data['id']
        
        # Verify DB
        self.assertEqual(Availability.objects.count(), 1)
        slot = Availability.objects.get(id=slot_id)
        self.assertEqual(slot.status, 'blocked')
        self.assertEqual(slot.start_at, start_at)
        self.assertEqual(slot.end_at, end_at)

        # 2. List with filter
        # Query that covers the slot
        res_list = self.client.get(f'/api/v1/availability/my/?from={start_at.date()}&to={end_at.date()}')
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data), 1)
        
        # Query outside range
        past_date = (now - timedelta(days=5)).date()
        res_empty = self.client.get(f'/api/v1/availability/my/?from={past_date}&to={past_date}')
        self.assertEqual(len(res_empty.data), 0)

        # 3. Delete
        res_del = self.client.delete(f'/api/v1/availability/{slot_id}/')
        self.assertEqual(res_del.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Availability.objects.count(), 0)

    def test_overlap_validation(self):
        """
        Ensure we cannot create overlapping slots.
        """
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        start1 = now + timedelta(days=2, hours=10)
        end1 = start1 + timedelta(hours=2) # 10:00 - 12:00
        
        # Create first slot
        self.client.post('/api/v1/availability/', {
            'start_at': start1.isoformat(),
            'end_at': end1.isoformat()
        })
        
        # Try create overlapping (11:00 - 13:00)
        start2 = start1 + timedelta(hours=1)
        end2 = start2 + timedelta(hours=2)
        
        res = self.client.post('/api/v1/availability/', {
            'start_at': start2.isoformat(),
            'end_at': end2.isoformat()
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Check specific error key if possible
        # Drf validation error structure: {'non_field_errors': ['...']} or field errors
        self.assertTrue(any("overlaps" in str(err) for err in res.data.values()) or "overlaps" in str(res.data))

        # Try create adjacent (12:00 - 14:00) - Should OK
        start3 = end1
        end3 = start3 + timedelta(hours=2)
        res_ok = self.client.post('/api/v1/availability/', {
            'start_at': start3.isoformat(),
            'end_at': end3.isoformat()
        })
        self.assertEqual(res_ok.status_code, status.HTTP_201_CREATED)

    def test_order_creates_busy_slot(self):
        """
        When an order is created (via creating Request -> Offer -> Order),
        a 'busy' availability slot should be created automatically with correct duration.
        """
        # 1. Create Request
        event_start = timezone.now() + timedelta(days=5, hours=14) # 14:00
        req = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            city="Almaty",
            event_date=event_start,
            event_start_at=event_start,
            title="Birthday"
        )
        
        # 2. Create Offer
        offer = Offer.objects.create(
            request=req,
            service=self.service,
            provider_profile=self.provider_profile,
            price=10000,
            status='accepted' # Pre-set for order creation
        )
        
        # 3. Create Order (Simulate)
        order = Order.objects.create(
            offer=offer,
            client=self.client_user,
            provider_profile=self.provider_profile,
            price_agreed=10000,
            status='confirmed'
        )
        
        # Verify busy slot
        self.assertTrue(Availability.objects.filter(order=order, status='busy').exists())
        slot = Availability.objects.get(order=order)
        
        self.assertEqual(slot.start_at, event_start)
        # End should be start + 90 mins
        expected_end = event_start + timedelta(minutes=90)
        self.assertEqual(slot.end_at, expected_end)
        
        # Verify provider cannot delete it (if restricted) - optional test based on permission logic
        # For now just verify created.

    def test_offer_blocked_if_busy(self):
        """
        Offer creation should fail if provider has overlapping availability.
        """
        # 1. Create overlapping availability
        now = timezone.now() + timedelta(days=10)
        Availability.objects.create(
            provider=self.provider_profile,
            start_at=now,
            end_at=now + timedelta(hours=2),
            status='blocked'
        )
        
        # 2. Create Request inside that time
        req = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            city="Almaty",
            event_date=now + timedelta(minutes=30),
            event_start_at=now + timedelta(minutes=30),
            title="Conflict",
            status='offers'
        )
        
        from apps.marketplace.serializers import OfferSerializer
        
        # Make context with provider user
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        request = factory.get('/')
        request.user = self.provider_user
        
        serializer = OfferSerializer(data={
            'request': req.id,
            'service': self.service.id,
            'price': 5000
        }, context={'request': request})
        
        self.assertFalse(serializer.is_valid())
        self.assertTrue('Time slot is manually blocked' in str(serializer.errors) or 'busy during this time' in str(serializer.errors))
