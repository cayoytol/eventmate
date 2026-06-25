from rest_framework import permissions


class IsProviderAuthenticated(permissions.BasePermission):
    """Check if user is authenticated and has provider_profile"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return hasattr(request.user, 'provider_profile')
