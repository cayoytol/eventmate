from rest_framework import serializers
from .models import Favorite
from apps.accounts.models import ProviderProfile
from apps.catalog.models import Service

class FavoriteToggleSerializer(serializers.Serializer):
    content_type = serializers.ChoiceField(choices=Favorite.ContentType.choices)
    object_id = serializers.IntegerField()

    def validate_content_type(self, value):
        if value not in [Favorite.ContentType.SERVICE, Favorite.ContentType.PROVIDER]:
            raise serializers.ValidationError("Invalid content_type.")
        return value

class FavoriteListSerializer(serializers.ModelSerializer):
    object_data = serializers.SerializerMethodField()

    class Meta:
        model = Favorite
        fields = ('id', 'content_type', 'object_id', 'object_data', 'created_at')

    def get_object_data(self, obj):
        request = self.context.get('request')
        service_map = self.context.get('service_map')
        provider_map = self.context.get('provider_map')

        if obj.content_type == Favorite.ContentType.SERVICE:
            if service_map is not None:
                service = service_map.get(obj.object_id)
            else:
                service = Service.objects.filter(id=obj.object_id).select_related('provider__user', 'category').first()
            if service:
                return {
                    "id": service.id,
                    "title": service.title,
                    "price_amount": service.price_amount,
                    "price_type": service.price_type,
                    "city": service.city,
                    "category_name": service.category.name_ru,
                    "provider": {
                        "id": service.provider.id,
                        "username": service.provider.user.username
                    },
                    "is_active": service.is_active
                }
        elif obj.content_type == Favorite.ContentType.PROVIDER:
            if provider_map is not None:
                profile = provider_map.get(obj.object_id)
            else:
                profile = ProviderProfile.objects.filter(id=obj.object_id).select_related('user').first()
            if profile:
                avatar_url = request.build_absolute_uri(profile.user.avatar.url) if request and profile.user.avatar else None
                return {
                    "id": profile.id,
                    "email": profile.user.email,
                    "username": profile.user.username,
                    "rating_avg": profile.rating_avg,
                    "reviews_count": profile.reviews_count,
                    "avatar": avatar_url,
                    "avatar_url": avatar_url,
                    "is_blocked": profile.is_blocked
                }
        return None
