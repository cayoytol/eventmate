from rest_framework import serializers
from django.utils import timezone
from .models import EventRequest, Offer, Order
from .utils import get_order_qr_capabilities


class EventRequestSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name_ru', read_only=True)
    target_service_id = serializers.IntegerField(required=False, write_only=True)
    chat_id = serializers.SerializerMethodField()
    budget_min = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False, allow_null=True)
    budget_max = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False, allow_null=True)
    
    class Meta:
        model = EventRequest
        fields = (
            'id', 'client', 'category', 'category_name', 'title', 'city', 
            'event_date', 'event_start_at', 'budget_min', 'budget_max', 'description', 'status', 
            'target_service_id', 'target_provider', 'target_service', 'created_at', 'chat_id'
        )
        read_only_fields = ('id', 'client', 'status', 'target_provider', 'target_service', 'created_at', 'chat_id')
        extra_kwargs = {
            'category': {'required': False}  # Optional when target_service_id provided
        }
    
    def get_chat_id(self, obj):
        """Return chat ID if exists (for targeted requests)"""
        chat = obj.chats.first()
        return chat.id if chat else None

    def validate_event_date(self, value):
        if value < timezone.now():
            raise serializers.ValidationError("Event date cannot be in the past.")
        return value
    
    def validate(self, attrs):
        # If target_service_id provided, category not required (will be auto-filled)
        target_service_id = attrs.get('target_service_id')
        category = attrs.get('category')
        
        if not target_service_id and not category:
            raise serializers.ValidationError({
                "category": "This field is required when not providing target_service_id"
            })
            
        budget_min = attrs.get('budget_min')
        budget_max = attrs.get('budget_max')
        
        if budget_min is not None and budget_max is not None:
            if budget_min > budget_max:
                raise serializers.ValidationError({
                    "budget_max": "budget_max must be greater than or equal to budget_min."
                })
        
        return attrs
    
    def create(self, validated_data):
        from apps.catalog.models import Service
        
        target_service_id = validated_data.pop('target_service_id', None)
        
        if target_service_id:
            try:
                service = Service.objects.select_related('provider', 'category').get(id=target_service_id)
                # Auto-fill from service
                validated_data['target_provider'] = service.provider
                validated_data['target_service'] = service
                validated_data['category'] = service.category
            except Service.DoesNotExist:
                raise serializers.ValidationError({"target_service_id": "Service not found"})
        
        return super().create(validated_data)

class EventRequestListSerializer(serializers.ModelSerializer):
    from apps.catalog.serializers import CategorySerializer
    
    category = CategorySerializer(read_only=True)
    offers_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = EventRequest
        fields = (
            'id', 'title', 'city', 'event_date', 
            'budget_min', 'budget_max', 'status', 
            'category', 'offers_count', 'created_at'
        )

class OfferSerializer(serializers.ModelSerializer):
    from apps.accounts.serializers import ProviderProfileBasicSerializer
    
    provider_name = serializers.CharField(source='provider_profile.user.email', read_only=True)
    service_title = serializers.CharField(source='service.title', read_only=True)
    provider = ProviderProfileBasicSerializer(source='provider_profile', read_only=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    
    class Meta:
        model = Offer
        fields = (
            'id', 'request', 'service', 'provider_profile', 'provider', 'provider_name',
            'service_title', 'price', 'cover_letter', 'status', 'created_at'
        )
        read_only_fields = ('id', 'provider_profile', 'provider', 'status', 'created_at')

    def validate(self, attrs):
        request_context = self.context.get('request')
        if not request_context:
            raise serializers.ValidationError("Request context is required.")
            
        user = request_context.user
        
        try:
            provider_profile = user.provider_profile
        except Exception:
             raise serializers.ValidationError("Provider profile not found. Keep calm and create a profile.")

        event_request = attrs.get('request')
        service = attrs.get('service')

        errors = {}
        if not event_request:
            errors['request'] = "This field is required."
        if not service:
            errors['service'] = "This field is required."
        
        if errors:
            raise serializers.ValidationError(errors)

        if event_request.status in [EventRequest.Status.CONFIRMED, EventRequest.Status.CANCELLED]:
            raise serializers.ValidationError("Request is closed.")
            
        if event_request.status != EventRequest.Status.OFFERS:
             raise serializers.ValidationError("Request is not accepting offers yet.")

        if event_request.client == user:
            raise serializers.ValidationError("You cannot create an offer for your own request.")

        if service.provider != provider_profile:
             raise serializers.ValidationError("You can only offer your own services.")

        from apps.accounts.models import Availability
        
        # Calculate start and end times
        start_at = event_request.event_start_at or event_request.event_date
        duration = getattr(service, 'duration_minutes', 60)
        from datetime import timedelta
        end_at = start_at + timedelta(minutes=duration)

        # Check for overlaps
        # 1. Check for manual blocks (strict)
        is_blocked = Availability.objects.filter(
            provider=provider_profile,
            start_at__lt=end_at,
            end_at__gt=start_at,
            status='blocked'
        ).exists()

        if is_blocked:
             raise serializers.ValidationError(f"Time slot is manually blocked ({start_at} - {end_at}).")

        # 2. Check capacity
        busy_count = Availability.objects.filter(
            provider=provider_profile,
            start_at__lt=end_at,
            end_at__gt=start_at,
            status='busy'
        ).count()
        
        capacity = getattr(service, 'capacity_per_slot', 1)
        
        if busy_count >= capacity:
            raise serializers.ValidationError(f"No capacity available. ({busy_count}/{capacity} slots taken).")

        return attrs

class EmptySerializer(serializers.Serializer):
    pass

class OrderProviderMinSerializer(serializers.Serializer):
    """Local minimal provider serializer"""
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    avatar_url = serializers.SerializerMethodField()

    def get_avatar_url(self, obj):
        try:
            if obj.user.avatar:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(obj.user.avatar.url)
                return obj.user.avatar.url
        except Exception:
            pass
        return None

class OrderListSerializer(serializers.ModelSerializer):
    provider = OrderProviderMinSerializer(source='provider_profile', read_only=True)
    client_email = serializers.EmailField(source='client.email', read_only=True)
    
    class Meta:
        model = Order
        fields = (
            'id', 'status', 'payment_status', 'price_agreed', 'provider', 
            'client_email', 'created_at'
        )

from .models import EventRequest, Offer, Order, Review, ReviewMedia

class ReviewMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewMedia
        fields = ('id', 'file_url', 'created_at')

class ReviewSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.email', read_only=True)
    media = ReviewMediaSerializer(many=True, read_only=True)
    
    class Meta:
        model = Review
        fields = ('id', 'rating', 'text', 'provider_reply', 'client_name', 'created_at', 'updated_at', 'media')

class ReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ('rating', 'text')
        
    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value

class ReviewReplySerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ('provider_reply',)

class OrderDetailSerializer(serializers.ModelSerializer):
    provider = OrderProviderMinSerializer(source='provider_profile', read_only=True)
    client_email = serializers.EmailField(source='client.email', read_only=True)
    review = ReviewSerializer(read_only=True)
    qr_capabilities = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = (
            'id', 'status', 'payment_status', 'price_agreed', 'provider', 'client_email',
            'service_snapshot', 'checkin_at', 'completed_at', 'created_at', 'review',
            'qr_capabilities'
        )

    def get_qr_capabilities(self, obj):
        request = self.context.get('request')
        user = request.user if (request and hasattr(request, 'user')) else None
        return get_order_qr_capabilities(obj, user)


class OrderActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True, allow_blank=False, max_length=500)

class OrderQRScanSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
