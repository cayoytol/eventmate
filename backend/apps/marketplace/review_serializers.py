from rest_framework import serializers
from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    """Serializer for Review"""
    client_email = serializers.EmailField(source='client.email', read_only=True)

    class Meta:
        model = Review
        fields = ('id', 'order', 'client', 'client_email', 'provider_profile', 'rating', 'text', 'provider_reply', 'created_at')
        read_only_fields = ('client', 'provider_profile', 'created_at')

    def validate_order(self, value):
        from .models import Order
        
        # Check if order is completed
        if value.status != Order.Status.COMPLETED:
            raise serializers.ValidationError("Reviews can only be created for completed orders.")
        
        # Check if user is the client of the order
        request = self.context.get('request')
        if request and value.client != request.user:
            raise serializers.ValidationError("You can only review your own orders.")
            
        # Check if review already exists (handled by OneToOneField, but good to have a clear error)
        if hasattr(value, 'review'):
            raise serializers.ValidationError("A review for this order already exists.")
            
        return value
