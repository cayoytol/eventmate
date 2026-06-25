from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from apps.core.media import build_absolute_media_url

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    provider_profile_id = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = (
            'id', 'email', 'phone', 'username', 'role', 
            'email_verified', 'phone_verified', 'language', 'avatar',
            'avatar_url', 'provider_profile_id', 'is_staff', 'is_superuser'
        )
        read_only_fields = (
            'id', 'email', 'phone', 'email_verified', 'phone_verified', 
            'provider_profile_id', 'is_staff', 'is_superuser', 'avatar', 'avatar_url'
        )
    
    def get_provider_profile_id(self, obj):
        """Return ProviderProfile.id if user is provider, else None"""
        if obj.role == 'provider' and hasattr(obj, 'provider_profile'):
            return obj.provider_profile.id
        return None

    def get_avatar_url(self, obj):
        return build_absolute_media_url(obj.avatar, self.context.get("request"))


class ProviderProfileBasicSerializer(serializers.ModelSerializer):
    """Lightweight provider profile for nested use in offers/services"""
    user = UserSerializer(read_only=True)
    
    class Meta:
        from apps.accounts.models import ProviderProfile
        model = ProviderProfile
        fields = ('id', 'bio', 'rating_avg', 'reviews_count', 'user')
        read_only_fields = fields

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ('email', 'username', 'password', 'role', 'phone')
        
    def validate_password(self, value):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
        
    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data.get('username', ''),
            password=validated_data['password'],
            role=validated_data.get('role', 'client'),
            phone=validated_data.get('phone', '')
        )
        
        # Auto-create ProviderProfile if role is provider
        if user.role == 'provider':
            from .models import ProviderProfile
            ProviderProfile.objects.get_or_create(user=user)
        
        return user

class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['email'] = user.email
        return token

class EmailVerifySerializer(serializers.Serializer):
    token = serializers.CharField()

class PhoneSendOtpSerializer(serializers.Serializer):
    phone = serializers.CharField()

class PhoneVerifyOtpSerializer(serializers.Serializer):
    phone = serializers.CharField()
    code = serializers.CharField(min_length=6, max_length=6)

class AvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        from apps.accounts.models import Availability
    order_capacity = serializers.SerializerMethodField()
    service_title = serializers.SerializerMethodField()

    class Meta:
        from apps.accounts.models import Availability
        model = Availability
        fields = ['id', 'start_at', 'end_at', 'status', 'order', 'order_capacity', 'service_title']
        read_only_fields = ['order', 'order_capacity', 'service_title']
        
    def get_order_capacity(self, obj):
        if obj.order and hasattr(obj.order, 'offer') and obj.order.offer.service:
            return getattr(obj.order.offer.service, 'capacity_per_slot', 1)
        return None

    def get_service_title(self, obj):
        if obj.order and hasattr(obj.order, 'offer') and obj.order.offer.service:
            return obj.order.offer.service.title
        return None
        
    def validate(self, data):
        start_at = data.get('start_at')
        end_at = data.get('end_at')
        
        if start_at and end_at:
            if start_at >= end_at:
                raise serializers.ValidationError("End time must be after start time.")
            
            # Check overlap
            from apps.accounts.models import Availability
            request = self.context.get('request')
            qs = Availability.objects.filter(
                provider=request.user.provider_profile,
                start_at__lt=end_at,
                end_at__gt=start_at
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
                
            if qs.exists():
                raise serializers.ValidationError("This time slot overlaps with an existing one.")
                
        return data


class ProviderPublicProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    avatar = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()

    class Meta:
        from apps.accounts.models import ProviderProfile
        model = ProviderProfile
        fields = ("id", "username", "avatar", "avatar_url", "bio", "city", "rating_avg", "reviews_count", "is_favorite")
        read_only_fields = fields

    def get_avatar(self, obj):
        try:
            if obj.user.avatar:
                request = self.context.get("request")
                if request:
                    return request.build_absolute_uri(obj.user.avatar.url)
                return obj.user.avatar.url
        except Exception:
            pass
        return None

    def get_avatar_url(self, obj):
        return self.get_avatar(obj)


    def get_city(self, obj):
        if hasattr(obj, 'city') and obj.city:
            return obj.city
        # Fallback to the provider's first service's city if it exists
        service = obj.services.first()
        if service:
            return service.city
        return None

    def get_is_favorite(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            from apps.favorites.models import Favorite
            return Favorite.objects.filter(
                user=request.user,
                content_type=Favorite.ContentType.PROVIDER,
                object_id=obj.id
            ).exists()
        return False

