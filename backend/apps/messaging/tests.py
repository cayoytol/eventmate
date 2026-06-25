from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status

from apps.marketplace.models import EventRequest, Offer, Order
from apps.catalog.models import Service, Category
from apps.accounts.models import ProviderProfile
from apps.messaging.models import Chat, ChatMessage

User = get_user_model()


class ChatFlowTestCase(TestCase):
    """Test chat auto-creation, permissions, and order linking"""
    
    def setUp(self):
        self.client_api = APIClient()
        
        # Create users
        self.client_user = User.objects.create_user(email='client@test.com', password='testpass123')
        self.provider_user = User.objects.create_user(email='provider@test.com', password='testpass123', role='provider')
        self.other_provider_user = User.objects.create_user(email='other@test.com', password='testpass123', role='provider')
        
        # Create provider profiles
        self.provider = ProviderProfile.objects.create(
            user=self.provider_user,
            bio='Test bio'
        )
        self.other_provider = ProviderProfile.objects.create(
            user=self.other_provider_user,
            bio='Other bio'
        )
        
        # Create category and service
        self.category = Category.objects.create(name_ru='Фотография', name_en='Photography')
        self.service = Service.objects.create(
            provider=self.provider,
            title='Wedding Photography',
            category=self.category,
            city='Almaty',
            price_amount=50000,
            price_type='fixed'
        )
        
        self.event_date = timezone.now() + timedelta(days=30)
    
    def test_targeted_request_creates_chat_with_system_message(self):
        """When client creates targeted request, chat is auto-created with system message"""
        request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            city='Almaty',
            event_date=self.event_date,
            description='Need photographer',
            target_provider=self.provider,
            target_service=self.service
        )
        
        # Chat should exist
        self.assertTrue(Chat.objects.filter(request=request).exists())
        chat = Chat.objects.get(request=request)
        
        # Verify participants
        self.assertEqual(chat.client, self.client_user)
        self.assertEqual(chat.provider, self.provider)
        
        # System message exists
        system_messages = chat.messages.filter(is_system=True)
        self.assertTrue(system_messages.exists())
        self.assertIn(self.service.title, system_messages.first().content)
    
    def test_provider_sees_chat_other_provider_cannot(self):
        """Only target provider can access chat"""
        request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            city='Almaty',
            event_date=self.event_date,
            description='Test',
            target_provider=self.provider,
            target_service=self.service
        )
        
        chat = Chat.objects.get(request=request)
        
        # Provider can see chat
        self.client_api.force_authenticate(user=self.provider_user)
        response = self.client_api.get(f'/api/v1/chats/{chat.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Other provider gets 404 (not in queryset)
        self.client_api.force_authenticate(user=self.other_provider_user)
        response = self.client_api.get(f'/api/v1/chats/{chat.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_accept_offer_links_chat_to_order(self):
        """When offer accepted, chat.order is set and system message added"""
        request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            city='Almaty',
            event_date=self.event_date,
            description='Test',
            target_provider=self.provider,
            target_service=self.service
        )
        
        offer = Offer.objects.create(
            request=request,
            service=self.service,
            provider_profile=self.provider,
            price=50000
        )
        
        # Create order (simulating accept logic)
        order = Order.objects.create(
            offer=offer,
            client=self.client_user,
            provider_profile=self.provider,
            price_agreed=50000,
            service_snapshot={'title': self.service.title}
        )
        
        # Chat should be linked to order
        chat = Chat.objects.get(request=request)
        chat.refresh_from_db()
        self.assertEqual(chat.order, order)
        
        # System message about order created
        order_messages = chat.messages.filter(is_system=True, content__contains='Заказ')
        self.assertTrue(order_messages.exists())
        self.assertIn(str(order.id), order_messages.first().content)
    
    def test_send_message_appears_for_other_participant(self):
        """Messages sent by one participant appear for the other"""
        request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            city='Almaty',
            event_date=self.event_date,
            description='Test',
            target_provider=self.provider,
            target_service=self.service
        )
        
        chat = Chat.objects.get(request=request)
        
        # Client sends message
        self.client_api.force_authenticate(user=self.client_user)
        response = self.client_api.post(
            f'/api/v1/chats/{chat.id}/messages/',
            {'content': 'Hello provider!'}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Provider can see message
        self.client_api.force_authenticate(user=self.provider_user)
        response = self.client_api.get(f'/api/v1/chats/{chat.id}/messages/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        messages = response.data
        user_messages = [m for m in messages if not m['is_system']]
        self.assertEqual(len(user_messages), 1)
        self.assertEqual(user_messages[0]['content'], 'Hello provider!')
    
    def test_unauthorized_user_cannot_access_chat(self):
        """User not part of chat gets 404"""
        request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            city='Almaty',
            event_date=self.event_date,
            description='Test',
            target_provider=self.provider,
            target_service=self.service
        )
        
        chat = Chat.objects.get(request=request)
        
        # Random user (other_provider) cannot access
        self.client_api.force_authenticate(user=self.other_provider_user)
        response = self.client_api.get(f'/api/v1/chats/{chat.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Cannot send messages either
        response = self.client_api.post(
            f'/api/v1/chats/{chat.id}/messages/',
            {'content': 'Unauthorized message'}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_mark_read_functionality(self):
        """Mark read updates unread messages"""
        request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            city='Almaty',
            event_date=self.event_date,
            description='Test',
            target_provider=self.provider,
            target_service=self.service
        )
        
        chat = Chat.objects.get(request=request)
        
        # Provider sends message
        self.client_api.force_authenticate(user=self.provider_user)
        self.client_api.post(
            f'/api/v1/chats/{chat.id}/messages/',
            {'content': 'Hello client!'}
        )
        
        # Client marks as read
        self.client_api.force_authenticate(user=self.client_user)
        response = self.client_api.post(f'/api/v1/chats/{chat.id}/mark-read/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['marked_read'], 0)
        
        # Verify message is marked as read
        message = ChatMessage.objects.filter(chat=chat, sender=self.provider_user).first()
        self.assertIsNotNone(message.read_at)
