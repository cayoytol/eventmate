from rest_framework import serializers
from .models import Chat, ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.CharField(source='sender.email', read_only=True, allow_null=True)
    
    class Meta:
        model = ChatMessage
        fields = ['id', 'chat', 'sender', 'sender_email', 'content', 
                  'attachment_url', 'is_system', 'read_at', 'created_at']
        read_only_fields = ['chat', 'sender', 'is_system', 'created_at', 'sender_email']


class ChatSerializer(serializers.ModelSerializer):
    client_email = serializers.CharField(source='client.email', read_only=True)
    provider_email = serializers.CharField(source='provider.user.email', read_only=True)
    provider_name = serializers.CharField(source='provider.business_name', read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Chat
        fields = ['id', 'request', 'order', 'client', 'client_email', 
                  'provider', 'provider_email', 'provider_name', 'created_at', 'updated_at',
                  'last_message', 'unread_count']
        read_only_fields = ['client', 'provider', 'created_at', 'updated_at']
    
    def get_last_message(self, obj):
        last_msg = obj.messages.order_by('-created_at').first()
        if last_msg:
            return {
                'content': last_msg.content,
                'created_at': last_msg.created_at,
                'sender_email': last_msg.sender.email if last_msg.sender else 'System',
                'is_system': last_msg.is_system
            }
        return None
    
    def get_unread_count(self, obj):
        request_user = self.context.get('request').user
        return obj.messages.filter(
            read_at__isnull=True
        ).exclude(sender=request_user).count()
