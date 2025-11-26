# Boss_Conn/permissions.py

from rest_framework import permissions
from django.conf import settings

class ModuleAPIKeyPermission(permissions.BasePermission):
    """
    Only boss_magics (with module.api_key) may call /api/migrate/.
    """
    def has_permission(self, request, view):
        return request.META.get("HTTP_X_API_KEY") == settings.MODULE_API_KEY
