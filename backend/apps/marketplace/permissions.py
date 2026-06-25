from rest_framework import permissions


class IsRequestClient(permissions.BasePermission):
    """
    Доступ к заявке (и ее офферам) только автору заявки (client).
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(obj, "client_id", None) == request.user.id


class IsOfferProvider(permissions.BasePermission):
    """
    Доступ к офферу только его автору (provider_profile).
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # obj.provider_profile = ProviderProfile
        try:
            user_profile = request.user.provider_profile
        except Exception:
            return False

        return getattr(obj, "provider_profile_id", None) == user_profile.id


class IsProvider(permissions.BasePermission):
    """
    Роль provider обязательна (для создания оффера и т.п.).
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "role", None) == "provider"
