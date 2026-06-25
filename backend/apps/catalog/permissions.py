from rest_framework import permissions

class IsProviderOrReadOnly(permissions.BasePermission):
    """
    Чтение доступно всем.
    Изменение/создание — только авторизованному провайдеру и только своих объектов.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        # Только роль provider может создавать/редактировать услуги
        return getattr(request.user, "role", None) == "provider"

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        # Безопасное получение провайдера у объекта (на случай если это не Service)
        provider = getattr(obj, 'provider', None)
        
        # Если провайдера нет или это некорректная ссылка - запрещаем изменение
        if not provider or not hasattr(provider, "user_id"):
            return False

        # Проверяем, что ID пользователя в профиле провайдера совпадает с текущим user.id
        # obj.provider = ProviderProfile
        return provider.user_id == request.user.id


class IsProviderOrStaff(permissions.BasePermission):
    """
    Allow access to authenticated providers or staff members.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        return (
            getattr(request.user, "role", None) == "provider" or
            request.user.is_staff or
            request.user.is_superuser
        )
