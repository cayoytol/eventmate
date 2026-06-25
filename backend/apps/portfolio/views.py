import uuid
from rest_framework import viewsets, permissions, status, mixins
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from .models import PortfolioItem, PortfolioMedia
from .serializers import (
    PortfolioItemSerializer,
    PortfolioMediaSerializer,
    PortfolioMediaUploadSerializer,
)


class IsPortfolioOwner(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        # Block client users and non-providers from writing to portfolio
        from apps.accounts.models import ProviderProfile

        return ProviderProfile.objects.filter(user=request.user).exists()

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if hasattr(obj, "provider_profile"):
            return obj.provider_profile.user == request.user
        if hasattr(obj, "item"):
            return obj.item.provider_profile.user == request.user
        return False


class PortfolioItemViewSet(viewsets.ModelViewSet):
    queryset = PortfolioItem.objects.all().prefetch_related("media")
    serializer_class = PortfolioItemSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "provider_portfolio"]:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsPortfolioOwner()]

    def get_throttles(self):
        if self.action == "add_media":
            self.throttle_scope = "media_upload"
            from rest_framework.throttling import ScopedRateThrottle
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def perform_create(self, serializer):
        from apps.accounts.models import ProviderProfile
        from apps.billing.exceptions import PlanLimitReached
        from apps.billing import services as billing_services

        provider_profile = get_object_or_404(
            ProviderProfile, user=self.request.user
        )
        
        # Concurrency-safe portfolio limit check
        if not billing_services.check_portfolio_limit(provider_profile):
            raise PlanLimitReached("max_portfolio_items")
            
        serializer.save(provider_profile=provider_profile)

    @action(
        detail=True,
        methods=["post"],
        url_path="media",
        parser_classes=[MultiPartParser, FormParser],
    )
    def add_media(self, request, pk=None):
        item = self.get_object()

        # Limit check: max 10 media per item
        if item.media.count() >= 10:
            return Response(
                {"detail": "Maximum 10 media items allowed per portfolio item."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if "file" in request.FILES:
            serializer = PortfolioMediaUploadSerializer(
                data=request.data, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            processed = serializer.context["processed_image"]

            uuid_filename = f"{uuid.uuid4()}.{processed.extension}"
            content_file = ContentFile(
                processed.content.read(), name=uuid_filename
            )

            media_record = PortfolioMedia(
                item=item,
                file=content_file,
                file_url="",
                media_type=PortfolioMedia.MediaType.IMAGE,
                mime_type=processed.mime_type,
                file_size=processed.size,
                width=processed.width,
                height=processed.height,
            )

            # Pre-validate before writing to storage
            try:
                media_record.full_clean()
            except ValidationError as e:
                # Format to API error dict
                return Response(
                    {"detail": e.message_dict},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Atomic save block
            try:
                with transaction.atomic():
                    media_record.save()
            except Exception:
                # Clean up uploaded file if DB insertion fails
                if media_record.file and media_record.file.name:
                    try:
                        media_record.file.storage.delete(media_record.file.name)
                    except Exception:
                        pass
                return Response(
                    {"detail": "Failed to upload file to storage."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            read_serializer = PortfolioMediaSerializer(
                media_record, context={"request": request}
            )
            return Response(read_serializer.data, status=status.HTTP_201_CREATED)

        else:
            # Fallback to existing url-based portfolio creation
            serializer = PortfolioMediaSerializer(
                data=request.data, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(item=item)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=False,
        methods=["get"],
        url_path="providers/(?P<provider_id>[^/.]+)",
    )
    def provider_portfolio(self, request, provider_id=None):
        items = PortfolioItem.objects.filter(
            provider_profile_id=provider_id
        ).prefetch_related("media")
        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)


class PortfolioMediaViewSet(
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = PortfolioMedia.objects.all()
    serializer_class = PortfolioMediaSerializer
    permission_classes = [permissions.IsAuthenticated, IsPortfolioOwner]

    def perform_update(self, serializer):
        instance = self.get_object()
        old_file_name = instance.file.name if instance.file else None
        
        with transaction.atomic():
            updated_instance = serializer.save()
            
        new_file_name = updated_instance.file.name if updated_instance.file else None
        if old_file_name and old_file_name != new_file_name:
            def delete_old_file():
                try:
                    if default_storage.exists(old_file_name):
                        default_storage.delete(old_file_name)
                except Exception:
                    pass
            transaction.on_commit(delete_old_file)

    def get_throttles(self):
        if self.action == "replace_media":
            self.throttle_scope = "media_upload"
            from rest_framework.throttling import ScopedRateThrottle
            return [ScopedRateThrottle()]
        return super().get_throttles()

    @action(
        detail=True,
        methods=["post", "patch"],
        url_path="replace",
        parser_classes=[MultiPartParser, FormParser],
    )
    def replace_media(self, request, pk=None):
        media = self.get_object()

        if "file" not in request.FILES:
            return Response(
                {"detail": "No file was uploaded."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PortfolioMediaUploadSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        processed = serializer.context["processed_image"]

        uuid_filename = f"{uuid.uuid4()}.{processed.extension}"
        content_file = ContentFile(
            processed.content.read(), name=uuid_filename
        )

        old_file_name = media.file.name if media.file else None

        try:
            with transaction.atomic():
                media.file = content_file
                media.file_url = ""  # Clear external URL on upload replacement
                media.mime_type = processed.mime_type
                media.file_size = processed.size
                media.width = processed.width
                media.height = processed.height
                media.save()
        except Exception:
            # Rollback storage if DB update failed
            if media.file and media.file.name:
                try:
                    media.file.storage.delete(media.file.name)
                except Exception:
                    pass
            return Response(
                {"detail": "Failed to replace image in database."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Defer old file deletion until database commit succeeds
        if old_file_name:

            def delete_old_file():
                try:
                    if default_storage.exists(old_file_name):
                        default_storage.delete(old_file_name)
                except Exception:
                    pass

            transaction.on_commit(delete_old_file)

        read_serializer = self.get_serializer(media)
        return Response(read_serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        media = self.get_object()
        try:
            with transaction.atomic():
                media.delete()
        except Exception:
            return Response(
                {"detail": "Failed to delete media record."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
