from rest_framework import serializers
from django.utils.translation import get_language
from apps.core.media import build_absolute_media_url

from .models import (
    Category, Service, ServiceMedia
)
from apps.favorites.models import Favorite

from apps.accounts.models import ProviderProfile


def get_localized_category_name(category, request):
    lang = None

    # 1) check query params
    if request and hasattr(request, "query_params"):
        lang = request.query_params.get("lang")

    # 2) если пользователь залогинен — берём его язык
    if not lang and request and getattr(request, "user", None) and request.user.is_authenticated:
        lang = getattr(request.user, "language", None)

    # 3) иначе — из текущего языка Django (Accept-Language / middleware)
    if not lang:
        lang = (get_language() or "ru")[:2]

    if lang not in ("ru", "en", "kz"):
        lang = "ru"

    val = getattr(category, f"name_{lang}", None)
    return val if val else category.name_ru


class CategorySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "icon", "parent", "children")

    def get_name(self, obj):
        request = self.context.get("request")
        return get_localized_category_name(obj, request)

    def get_children(self, obj):
        qs = obj.children.all().order_by("name_ru")
        return CategorySerializer(qs, many=True, context=self.context).data


class ProviderProfileMinSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    avatar = serializers.ImageField(source="user.avatar", read_only=True)
    avatar_url = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()

    class Meta:
        model = ProviderProfile
        fields = ("id", "username", "avatar", "avatar_url", "rating_avg", "reviews_count", "is_favorite")

    def get_avatar_url(self, obj):
        return build_absolute_media_url(obj.user.avatar, self.context.get("request"))


    def get_is_favorite(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(
                user=request.user,
                content_type=Favorite.ContentType.PROVIDER,
                object_id=obj.id
            ).exists()
        return False


class ServiceMediaSerializer(serializers.ModelSerializer):
    cover_url = serializers.SerializerMethodField()

    class Meta:
        model = ServiceMedia
        fields = ("id", "file", "is_cover", "cover_url")

    def get_cover_url(self, obj):
        return build_absolute_media_url(obj.file, self.context.get("request"))


class ServiceListSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    cover = serializers.SerializerMethodField()
    provider = ProviderProfileMinSerializer(read_only=True)
    is_favorite = serializers.SerializerMethodField()
    distance_m = serializers.SerializerMethodField()

    cover_url = serializers.SerializerMethodField()
    cover_media_id = serializers.SerializerMethodField()
    cover_width = serializers.SerializerMethodField()
    cover_height = serializers.SerializerMethodField()
    cover_mime_type = serializers.SerializerMethodField()
    cover_file_size = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = (
            "id", "title", "price_amount", "price_type", "city", "address",
            "category", "category_name",
            "cover", "provider",
            "is_favorite", "is_active",
            "latitude", "longitude",
            "created_at",
            "distance_m",
            "cover_url",
            "cover_media_id",
            "cover_width",
            "cover_height",
            "cover_mime_type",
            "cover_file_size",
        )

    def get_category_name(self, obj):
        request = self.context.get("request")
        return get_localized_category_name(obj.category, request)

    def _get_active_cover(self, obj):
        if not hasattr(obj, "_active_cover"):
            media_list = list(obj.media.all())
            
            # 1. Try explicit cover first and verify physical file (Task 9)
            cover = next((m for m in media_list if m.is_cover), None)
            if cover and cover.file:
                try:
                    if cover.file.storage.exists(cover.file.name):
                        obj._active_cover = cover
                        return obj._active_cover
                except Exception:
                    pass
            
            # 2. Try first valid service image with physical file
            for media in media_list:
                if media.file:
                    try:
                        if media.file.storage.exists(media.file.name):
                            obj._active_cover = media
                            return obj._active_cover
                    except Exception:
                        pass
            
            # 3. No valid physical image found
            obj._active_cover = None
        return obj._active_cover

    def get_cover(self, obj):
        cover = self._get_active_cover(obj)
        if not cover or not cover.file:
            return None
        return build_absolute_media_url(cover.file, self.context.get("request"))

    def get_cover_url(self, obj):
        return self.get_cover(obj)

    def get_cover_media_id(self, obj):
        cover = self._get_active_cover(obj)
        return cover.id if cover else None

    def get_cover_width(self, obj):
        cover = self._get_active_cover(obj)
        return cover.width if cover else None

    def get_cover_height(self, obj):
        cover = self._get_active_cover(obj)
        return cover.height if cover else None

    def get_cover_mime_type(self, obj):
        cover = self._get_active_cover(obj)
        return cover.mime_type if cover else ""

    def get_cover_file_size(self, obj):
        cover = self._get_active_cover(obj)
        return cover.file_size if cover else None

    def get_is_favorite(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(
                user=request.user, 
                content_type=Favorite.ContentType.SERVICE, 
                object_id=obj.id
            ).exists()
        return False

    def get_distance_m(self, obj):
        val = getattr(obj, "distance_m", None)
        if val is not None:
            return int(val)
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get("distance_m") is None:
            data.pop("distance_m", None)
        return data


class ServiceDetailSerializer(ServiceListSerializer):
    media = ServiceMediaSerializer(many=True, read_only=True)

    class Meta(ServiceListSerializer.Meta):
        fields = ServiceListSerializer.Meta.fields + ("description", "media", "latitude", "longitude")


class ServiceCreateSerializer(serializers.ModelSerializer):
    price_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)

    class Meta:
        model = Service
        fields = (
            "id", "category", "title", "description", "price_type",
            "price_amount", "city", "address", "latitude", "longitude", "is_active"
        )
        read_only_fields = ("created_at", "provider")

    def validate(self, attrs):
        request = self.context.get("request")
        is_patch = request and request.method == "PATCH"

        if is_patch:
            req_has_lat = "latitude" in request.data
            req_has_lng = "longitude" in request.data

            if not req_has_lat and not req_has_lng:
                pass
            elif req_has_lat != req_has_lng:
                raise serializers.ValidationError(
                    "Both latitude and longitude must be provided together, or both must be omitted."
                )
            else:
                val_lat = request.data.get("latitude")
                val_lng = request.data.get("longitude")

                if (val_lat is None) != (val_lng is None):
                    raise serializers.ValidationError(
                        "Both latitude and longitude must be set to null together, or both must be valid numbers."
                    )

                if val_lat is None and val_lng is None:
                    attrs["latitude"] = None
                    attrs["longitude"] = None
                else:
                    try:
                        lat_num = float(val_lat)
                        lng_num = float(val_lng)
                    except (ValueError, TypeError):
                        raise serializers.ValidationError("Latitude and longitude must be valid numbers.")

                    if not (-90 <= lat_num <= 90):
                        raise serializers.ValidationError("Latitude must be between -90 and 90.")
                    if not (-180 <= lng_num <= 180):
                        raise serializers.ValidationError("Longitude must be between -180 and 180.")

                    attrs["latitude"] = lat_num
                    attrs["longitude"] = lng_num
        else:
            val_lat = attrs.get("latitude")
            val_lng = attrs.get("longitude")

            if (val_lat is None) != (val_lng is None):
                raise serializers.ValidationError(
                    "Both latitude and longitude must be provided together, or both must be omitted."
                )

            if val_lat is not None and val_lng is not None:
                try:
                    lat_num = float(val_lat)
                    lng_num = float(val_lng)
                except (ValueError, TypeError):
                    raise serializers.ValidationError("Latitude and longitude must be valid numbers.")

                if not (-90 <= lat_num <= 90):
                    raise serializers.ValidationError("Latitude must be between -90 and 90.")
                if not (-180 <= lng_num <= 180):
                    raise serializers.ValidationError("Longitude must be between -180 and 180.")

                attrs["latitude"] = lat_num
                attrs["longitude"] = lng_num

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        try:
            provider_profile = user.provider_profile
        except Exception:
            raise serializers.ValidationError("Provider profile not found. Switch role to provider / create provider profile.")

        validated_data["provider"] = provider_profile
        return super().create(validated_data)
