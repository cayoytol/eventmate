from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import ServiceComment
from .serializers import ServiceCommentSerializer
from apps.catalog.models import Service

class IsAuthorOrServiceProviderOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        
        # Author can edit or delete
        if obj.user == request.user:
            return True
            
        # Service provider owner can only delete
        if request.method == 'DELETE' and obj.service.provider.user == request.user:
            return True
            
        return False

class ServiceCommentViewSet(viewsets.ModelViewSet):
    queryset = ServiceComment.objects.all().select_related('user', 'service__provider').prefetch_related('replies', 'replies__user')
    serializer_class = ServiceCommentSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        if self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsAuthorOrServiceProviderOrAdmin()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        service_id = self.kwargs.get('service_id')
        if service_id:
            # Filter root comments for the service (parent is null)
            return qs.filter(service_id=service_id, parent__isnull=True)
        return qs

    def perform_create(self, serializer):
        service_id = self.kwargs.get('service_id')
        service = get_object_or_404(Service, pk=service_id)
        parent = serializer.validated_data.get('parent')

        if parent:
            # Logic: Only service owner can reply
            if service.provider.user != self.request.user:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Only the service provider can reply to comments.")
            
            # Logic: Reply inherits service from parent
            if parent.service_id != service.id:
                from rest_framework.exceptions import ValidationError
                raise ValidationError("Parent comment belongs to a different service.")

        serializer.save(user=self.request.user, service=service)

    def perform_destroy(self, instance):
        # Soft delete
        instance.is_deleted = True
        instance.text = ""
        instance.save(update_fields=['is_deleted', 'text'])

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_deleted:
            return Response(
                {"detail": "Cannot edit a deleted comment."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # New Rule: Cannot edit root comment if it has replies
        if instance.parent is None and instance.replies.exists():
            return Response(
                {"detail": "Cannot edit a root comment that already has replies."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        return super().partial_update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        # Restriction: Only text can be updated
        kwargs['partial'] = True
        return self.partial_update(request, *args, **kwargs)
