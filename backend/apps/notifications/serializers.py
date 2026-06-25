from rest_framework import serializers
from .models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('id', 'title', 'message', 'type', 'payload', 'is_read', 'created_at')
        read_only_fields = ('id', 'title', 'message', 'type', 'payload', 'created_at')
