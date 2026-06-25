from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from .models import Chat, ChatMessage
from .serializers import ChatSerializer, ChatMessageSerializer


class IsChatParticipant(permissions.BasePermission):
    """Only chat client or provider can access"""
    
    def has_object_permission(self, request, view, obj):
        # obj is Chat
        if request.user == obj.client:
            return True
        if hasattr(request.user, 'provider_profile') and request.user.provider_profile == obj.provider:
            return True
        return False


class ChatViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Chats with nested message endpoints.
    
    GET /api/v1/chats/ - list user's chats
    GET /api/v1/chats/{id}/ - retrieve chat details
    GET /api/v1/chats/{id}/messages/ - list messages
    POST /api/v1/chats/{id}/messages/ - send message
    POST /api/v1/chats/{id}/mark-read/ - mark messages as read
    """
    serializer_class = ChatSerializer
    permission_classes = [permissions.IsAuthenticated, IsChatParticipant]
    
    def get_queryset(self):
        user = self.request.user
        
        # Client's chats
        client_chats = Q(client=user)
        
        # Provider's chats
        provider_chats = Q()
        if hasattr(user, 'provider_profile'):
            provider_chats = Q(provider=user.provider_profile)
        
        return Chat.objects.filter(
            client_chats | provider_chats
        ).select_related('client', 'provider__user', 'request', 'order')
    
    @action(detail=True, methods=['get', 'post'])
    def messages(self, request, pk=None):
        """
        GET /api/v1/chats/{id}/messages/ - list messages in chat
        POST /api/v1/chats/{id}/messages/ - send message
        """
        chat = self.get_object()  # Triggers permission check
        
        if request.method == 'GET':
            messages = ChatMessage.objects.filter(
                chat=chat
            ).select_related('sender').order_by('created_at')
            serializer = ChatMessageSerializer(messages, many=True)
            return Response(serializer.data)
        
        elif request.method == 'POST':
            serializer = ChatMessageSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Set sender and chat
            message = serializer.save(
                sender=request.user,
                chat=chat
            )
            
            # Update chat.updated_at
            chat.save(update_fields=['updated_at'])
            
            return Response(
                ChatMessageSerializer(message).data,
                status=status.HTTP_201_CREATED
            )
    
    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """POST /api/v1/chats/{id}/mark-read/ - mark all unread messages as read"""
        chat = self.get_object()  # Triggers permission check
        
        # Mark messages where sender != current user
        updated = ChatMessage.objects.filter(
            chat=chat,
            read_at__isnull=True
        ).exclude(sender=request.user).update(read_at=timezone.now())
        
        return Response({'marked_read': updated})
