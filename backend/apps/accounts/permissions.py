from rest_framework import permissions

class IsNotBlockedProvider(permissions.BasePermission):
    """
    Запрещает доступ, если провайдер заблокирован.
    """
    message = "Your provider profile is blocked."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
            
        # Проверяем наличие профиля провайдера и статус блокировки
        if hasattr(user, 'provider_profile'):
            return not user.provider_profile.is_blocked
            
        return True
