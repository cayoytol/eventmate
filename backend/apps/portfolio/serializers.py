from rest_framework import serializers
from apps.core.media import validate_and_process_image, build_absolute_media_url
from django.core.exceptions import ValidationError
from .models import PortfolioItem, PortfolioMedia


class PortfolioMediaSerializer(serializers.ModelSerializer):
    uploaded_url = serializers.SerializerMethodField()
    external_url = serializers.SerializerMethodField()
    resolved_url = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioMedia
        fields = (
            "id",
            "file_url",
            "media_type",
            "uploaded_url",
            "external_url",
            "resolved_url",
            "width",
            "height",
            "mime_type",
            "file_size",
            "created_at",
        )

    def get_uploaded_url(self, obj):
        return build_absolute_media_url(obj.file, self.context.get("request"))

    def get_external_url(self, obj):
        return obj.file_url or ""

    def get_resolved_url(self, obj):
        uploaded = self.get_uploaded_url(obj)
        if uploaded:
            return uploaded
        return obj.file_url or ""

    def validate(self, attrs):
        instance = self.instance
        file = attrs.get("file", instance.file if instance else None)
        file_url = attrs.get("file_url", instance.file_url if instance else "")

        has_file = bool(file)
        has_url = bool(file_url)

        if not has_file and not has_url:
            raise serializers.ValidationError(
                "Exactly one of 'file' or 'file_url' must be provided."
            )
        if has_file and has_url:
            raise serializers.ValidationError(
                "Provide either 'file' or 'file_url', not both."
            )

        return attrs


class PortfolioMediaUploadSerializer(serializers.Serializer):
    file = serializers.ImageField(required=True)

    def validate_file(self, value):
        try:
            # Reusable core validation
            processed = validate_and_process_image(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.message)
        except Exception:
            raise serializers.ValidationError("Failed to validate image.")

        self.context["processed_image"] = processed
        return value


class PortfolioItemSerializer(serializers.ModelSerializer):
    media = PortfolioMediaSerializer(many=True, read_only=True)
    cover_url = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioItem
        fields = (
            "id",
            "provider_profile",
            "title",
            "description",
            "media",
            "cover_url",
            "created_at",
        )
        read_only_fields = ("provider_profile", "created_at")

    def get_cover_url(self, obj):
        request = self.context.get("request")
        # Image selection logic for portfolio:
        # 1. First valid portfolio image
        # 2. Check if physical file exists in storage to avoid broken links (Task 9)
        for media in obj.media.all():
            if media.media_type == "image":
                if media.file:
                    try:
                        if media.file.storage.exists(media.file.name):
                            return build_absolute_media_url(media.file, request)
                    except Exception:
                        pass
                elif media.file_url:
                    # External URL
                    return media.file_url
        return None

    def validate(self, data):
        return data
