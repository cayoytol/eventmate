from rest_framework import viewsets, permissions, filters, views, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db.models import Q

from .models import Category, Service
from .serializers import (
    CategorySerializer,
    ServiceListSerializer, ServiceDetailSerializer, ServiceCreateSerializer
)
from .filters import ServiceFilter
from .permissions import IsProviderOrReadOnly, IsProviderOrStaff
from apps.accounts.models import ProviderProfile
from apps.accounts.permissions import IsNotBlockedProvider


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        # list -> корневые, retrieve -> любые (через дефолтный get_object)
        if self.action == "list":
            return Category.objects.filter(parent__isnull=True).prefetch_related("children")
        return Category.objects.all().prefetch_related("children")

    serializer_class = CategorySerializer


from rest_framework.pagination import PageNumberPagination
from .geo_filters import GeoFilterBackend

class ServicePagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100

class ServiceViewSet(viewsets.ModelViewSet):
    pagination_class = ServicePagination

    
    def get_permissions(self):
        # Public endpoints (list/retrieve) - Allow fetch without auth
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
            
        # Protected write endpoints (create/update/delete)
        return [permissions.IsAuthenticated(), IsProviderOrReadOnly(), IsNotBlockedProvider()]

    def get_throttles(self):
        if self.action == "cover" and self.request.method == "POST":
            self.throttle_scope = "media_upload"
            from rest_framework.throttling import ScopedRateThrottle
            return [ScopedRateThrottle()]
        return super().get_throttles()

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter, GeoFilterBackend]
    filterset_class = ServiceFilter
    search_fields = ["title", "description", "city"]
    ordering_fields = ["price_amount", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = (
            Service.objects
            .select_related("provider__user", "category")
            .prefetch_related("media")
        )

        user = getattr(self.request, "user", None)

        # Check for explicit provider=me filter (My Services page)
        if self.request.query_params.get("provider") == "me":
            if not user or not user.is_authenticated:
                return qs.none()  # Unauthenticated users have no "my services"
            
            if getattr(user, "role", None) == "provider":
                try:
                    my_profile = user.provider_profile
                    # Return ONLY this provider's services (all statuses)
                    return qs.filter(provider=my_profile)
                except (AttributeError, ProviderProfile.DoesNotExist):
                    # User has provider role but no ProviderProfile
                    return qs.none()
            
            # Non-providers have no services
            return qs.none()

        # 1. Гость/неавторизованный: только активные и незаблокированные провайдеры
        if not user or not user.is_authenticated:
            return qs.filter(is_active=True, provider__is_blocked=False)

        # 2. Провайдер: видит только активные чужие (незаблокированные) + СВОИ любые (даже если заблокирован)
        if getattr(user, "role", None) == "provider":
            try:
                my_profile = user.provider_profile
                if user.is_staff:
                    return qs.filter(Q(is_active=True) | Q(provider=my_profile))
                return qs.filter(
                    Q(is_active=True, provider__is_blocked=False) | Q(provider=my_profile)
                )
            except (AttributeError, ProviderProfile.DoesNotExist):
                if user.is_staff:
                    return qs.filter(is_active=True)
                return qs.filter(is_active=True, provider__is_blocked=False)

        # 3. Клиент: только активные незаблокированные (или все активные для staff)
        if user.is_staff:
            return qs.filter(is_active=True)
        return qs.filter(is_active=True, provider__is_blocked=False)



    def get_serializer_class(self):
        if self.action == "retrieve":
            return ServiceDetailSerializer
        if self.action == "list":
            return ServiceListSerializer
        return ServiceCreateSerializer

    def perform_create(self, serializer):
        """Create service with safe provider profile handling"""
        from rest_framework.exceptions import PermissionDenied
        from django.conf import settings
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Validate user has provider role
        if getattr(self.request.user, 'role', None) != 'provider':
            raise PermissionDenied("Only providers can create services.")
        
        # Safe get or create provider profile
        provider_profile, created = ProviderProfile.objects.get_or_create(
            user=self.request.user
        )
        
        # Check billing limit before creating service
        # Only skip billing check if module/tables don't exist AND we're in DEBUG mode
        try:
            from apps.billing.exceptions import PlanLimitReached
            from apps.billing import services as billing_services
            if not billing_services.check_service_limit(provider_profile):
                raise PlanLimitReached("max_active_services")
        except PlanLimitReached:
            raise
        except (ModuleNotFoundError, ImportError):
            # Billing module not installed - only allow in DEBUG mode
            if settings.DEBUG:
                logger.warning("Billing module not found, allowing service creation in DEBUG mode")
            else:
                raise PermissionDenied("Billing system unavailable")
        except Exception as e:
            # Check if it's a database error (tables don't exist)
            from django.db.utils import ProgrammingError, OperationalError
            if isinstance(e, (ProgrammingError, OperationalError)):
                # Database tables missing - only allow in DEBUG mode
                if settings.DEBUG:
                    logger.warning(f"Billing tables not found: {e}, allowing service creation in DEBUG mode")
                else:
                    raise PermissionDenied("Billing system not configured")
            else:
                # All other errors are real problems - re-raise them
                logger.error(f"Billing check failed with unexpected error: {e}")
                raise
        
        serializer.save(provider=provider_profile)

    @action(
        detail=True,
        methods=["post", "delete"],
        url_path="cover",
        parser_classes=[MultiPartParser, FormParser],
    )
    def cover(self, request, pk=None):
        from rest_framework.exceptions import PermissionDenied
        from django.core.exceptions import ValidationError
        from django.db import transaction, IntegrityError
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile
        from apps.core.media import validate_and_process_image, generate_image_storage_name
        from .models import ServiceMedia
        from .serializers import ServiceMediaSerializer
        from rest_framework.parsers import MultiPartParser, FormParser
        import uuid

        service = self.get_object()

        # 1. Ownership validation
        if service.provider.user != request.user:
            return Response(
                {"detail": "You do not own this service."},
                status=status.HTTP_403_FORBIDDEN
            )

        if request.method == "POST":
            if "file" not in request.FILES:
                return Response(
                    {"detail": "No file was uploaded."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            uploaded_file = request.FILES["file"]
            
            try:
                # Authoritative processing
                processed = validate_and_process_image(uploaded_file)
            except ValidationError as e:
                return Response(
                    {"detail": e.message},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception:
                return Response(
                    {"detail": "Failed to process image."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Generate final storage name using the ProcessedImage extension Authoritative
            provider_id = service.provider.id
            final_name = generate_image_storage_name(
                prefix="services",
                owner_id=provider_id,
                resource_id=service.id,
                extension=processed.extension,
            )

            # Save to storage first
            try:
                saved_name = default_storage.save(final_name, ContentFile(processed.content.read()))
            except Exception:
                return Response(
                    {"detail": "Failed to save file to storage."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # DB work
            try:
                with transaction.atomic():
                    # select_for_update locking
                    locked_service = Service.objects.select_for_update().get(pk=service.pk)
                    
                    # Retrieve the current active cover
                    old_cover = ServiceMedia.objects.filter(service=locked_service, is_cover=True).first()
                    old_file_name = old_cover.file.name if old_cover else None

                    if old_cover:
                        # Update the existing cover row in place
                        old_cover.file.name = saved_name
                        old_cover.mime_type = processed.mime_type
                        old_cover.file_size = processed.size
                        old_cover.width = processed.width
                        old_cover.height = processed.height
                        old_cover.save()
                        cover_record = old_cover
                    else:
                        # Create a new cover row
                        cover_record = ServiceMedia.objects.create(
                            service=locked_service,
                            file=saved_name,
                            is_cover=True,
                            mime_type=processed.mime_type,
                            file_size=processed.size,
                            width=processed.width,
                            height=processed.height,
                        )
            except IntegrityError:
                # Cleanup newly written file if constraint fails
                try:
                    default_storage.delete(saved_name)
                except Exception:
                    pass
                return Response(
                    {"detail": "Database integrity error. Duplicate cover exists."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception:
                # Cleanup newly written file on db failure
                try:
                    default_storage.delete(saved_name)
                except Exception:
                    pass
                return Response(
                    {"detail": "Failed to save cover image to database."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # On success: delete old cover file from storage
            if old_file_name and old_file_name != saved_name:
                def delete_old_file():
                    try:
                        if default_storage.exists(old_file_name):
                            default_storage.delete(old_file_name)
                    except Exception:
                        pass
                transaction.on_commit(delete_old_file)

            read_serializer = ServiceMediaSerializer(cover_record, context={"request": request})
            return Response(read_serializer.data, status=status.HTTP_201_CREATED)

        elif request.method == "DELETE":
            try:
                with transaction.atomic():
                    # lock Service
                    locked_service = Service.objects.select_for_update().get(pk=service.pk)
                    
                    # Find active cover
                    cover_record = ServiceMedia.objects.filter(service=locked_service, is_cover=True).first()
                    
                    if cover_record:
                        # Deletion of the storage file is handled by post_delete signal on commit
                        # Therefore, we ONLY delete the DB row here.
                        cover_record.delete()
            except Exception:
                return Response(
                    {"detail": "Failed to delete cover image."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            return Response(status=status.HTTP_204_NO_CONTENT)


class GeocodeView(views.APIView):
    permission_classes = [IsProviderOrStaff]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'provider_geocoding'

    def post(self, request, *args, **kwargs):
        from django.conf import settings
        from rest_framework import status
        from .geocoding import geocode_address

        if not settings.DGIS_GEOCODING_ENABLED:
            return Response(
                {"detail": "Geocoding service is currently disabled."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        query = request.data.get("query")
        city = request.data.get("city")
        locale = request.data.get("locale", "ru")

        if not query:
            return Response(
                {"detail": "Query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        query = str(query).strip()
        if len(query) < 3:
            return Response(
                {"detail": "Query must be at least 3 characters long."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(query) > settings.DGIS_GEOCODING_MAX_QUERY_LENGTH:
            return Response(
                {"detail": f"Query must not exceed {settings.DGIS_GEOCODING_MAX_QUERY_LENGTH} characters."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if locale not in ("ru", "en", "kz"):
            return Response(
                {"detail": "Locale must be one of: ru, en, kz."},
                status=status.HTTP_400_BAD_REQUEST
            )

        results = geocode_address(query, locale, city=city)
        return Response({"results": results})


class ReverseGeocodeView(views.APIView):
    permission_classes = [IsProviderOrStaff]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'provider_geocoding'

    def post(self, request, *args, **kwargs):
        from django.conf import settings
        from rest_framework import status
        from .geocoding import reverse_geocode

        if not settings.DGIS_GEOCODING_ENABLED:
            return Response(
                {"detail": "Geocoding service is currently disabled."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")
        locale = request.data.get("locale", "ru")

        if latitude is None or longitude is None:
            return Response(
                {"detail": "Both latitude and longitude are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            lat = float(latitude)
            lng = float(longitude)
        except (ValueError, TypeError):
            return Response(
                {"detail": "Latitude and longitude must be valid numbers."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not (-90 <= lat <= 90):
            return Response(
                {"detail": "Latitude must be between -90 and 90."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not (-180 <= lng <= 180):
            return Response(
                {"detail": "Longitude must be between -180 and 180."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if locale not in ("ru", "en", "kz"):
            return Response(
                {"detail": "Locale must be one of: ru, en, kz."},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = reverse_geocode(lat, lng, locale)
        return Response({"result": result})
