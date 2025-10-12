from rest_framework import permissions


class IsModerator(permissions.BasePermission):
    """Разрешение для модераторов (is_staff=True)"""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsAdmin(permissions.BasePermission):
    """Разрешение для администраторов (is_superuser=True)"""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)


class IsModeratorOrAdmin(permissions.BasePermission):
    """Разрешение для модераторов или администраторов"""
    def has_permission(self, request, view):
        return bool(request.user and (request.user.is_staff or request.user.is_superuser))


class IsOwnerOrModerator(permissions.BasePermission):
    """Разрешение для владельца объекта или модератора"""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
    
    def has_object_permission(self, request, view, obj):
        # Модератор или админ имеют доступ ко всем объектам
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Владелец имеет доступ к своим объектам
        if hasattr(obj, 'creator'):
            return obj.creator == request.user
        
        return False


