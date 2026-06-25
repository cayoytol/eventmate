from rest_framework import permissions


class IsPaymentOwner(permissions.BasePermission):
    """Check if user is the owner of the payment"""
    
    def has_object_permission(self, request, view, obj):
        # Check if user has provider_profile
        if not hasattr(request.user, 'provider_profile'):
            return False
        
        # Check if payment belongs to this provider
        return obj.provider_profile == request.user.provider_profile
