from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Favorite
from .serializers import FavoriteToggleSerializer, FavoriteListSerializer

class IsClientRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'client'

class FavoriteViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsClientRole]
    serializer_class = FavoriteListSerializer

    def get_queryset(self):
        qs = Favorite.objects.filter(user=self.request.user)
        fav_type = self.request.query_params.get('type', 'all')
        
        if fav_type == 'service':
            qs = qs.filter(content_type=Favorite.ContentType.SERVICE)
        elif fav_type == 'provider':
            qs = qs.filter(content_type=Favorite.ContentType.PROVIDER)
            
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            context = self.get_serializer_context()
            context.update(self._get_bulk_maps(page))
            serializer = self.get_serializer(page, many=True, context=context)
            return self.get_paginated_response(serializer.data)
            
        context = self.get_serializer_context()
        context.update(self._get_bulk_maps(queryset))
        serializer = self.get_serializer(queryset, many=True, context=context)
        return Response(serializer.data)

    def _get_bulk_maps(self, favorites):
        from apps.catalog.models import Service
        from apps.accounts.models import ProviderProfile
        
        service_ids = [fav.object_id for fav in favorites if fav.content_type == Favorite.ContentType.SERVICE]
        provider_ids = [fav.object_id for fav in favorites if fav.content_type == Favorite.ContentType.PROVIDER]
        
        service_map = {}
        if service_ids:
            service_map = Service.objects.select_related('provider__user', 'category').in_bulk(service_ids)
            
        provider_map = {}
        if provider_ids:
            provider_map = ProviderProfile.objects.select_related('user').in_bulk(provider_ids)
            
        return {
            'service_map': service_map,
            'provider_map': provider_map
        }

    @action(detail=False, methods=['post'])
    def toggle(self, request):
        user = request.user
        
        # 1. 403 Forbidden: Only Client role can favorite
        if user.role != 'client':
            return Response(
                {"detail": "Only users with 'client' role can add to favorites."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = FavoriteToggleSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        content_type = data['content_type']
        object_id = data['object_id']

        # 2. 403 Forbidden/404 Not Found checks
        from apps.catalog.models import Service
        from apps.accounts.models import ProviderProfile

        if content_type == Favorite.ContentType.SERVICE:
            if not Service.objects.filter(id=object_id).exists():
                return Response({"detail": f"Service with id {object_id} not found."}, status=status.HTTP_404_NOT_FOUND)
        
        elif content_type == Favorite.ContentType.PROVIDER:
            try:
                profile = ProviderProfile.objects.get(id=object_id)
            except ProviderProfile.DoesNotExist:
                return Response({"detail": f"Provider with id {object_id} not found."}, status=status.HTTP_404_NOT_FOUND)
            
            # 403 Forbidden: Cannot favorite self
            if hasattr(user, 'provider_profile') and user.provider_profile.id == profile.id:
                return Response({"detail": "You cannot add yourself to favorites."}, status=status.HTTP_403_FORBIDDEN)
        
        # 3. Perform Toggle
        fav, created = Favorite.objects.get_or_create(
            user=user,
            content_type=content_type,
            object_id=object_id
        )
        
        if not created:
            fav.delete()
            return Response({"status": "removed"}, status=status.HTTP_200_OK)
            
        return Response({"status": "added"}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def check(self, request):
        content_type = request.query_params.get('content_type')
        object_id = request.query_params.get('object_id')
        
        if not content_type or not object_id:
            return Response({"detail": "Provide content_type and object_id"}, status=status.HTTP_400_BAD_REQUEST)
            
        is_favorite = Favorite.objects.filter(
            user=request.user,
            content_type=content_type,
            object_id=object_id
        ).exists()
        
        return Response({"is_favorite": is_favorite})
