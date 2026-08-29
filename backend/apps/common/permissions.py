from rest_framework.permissions import BasePermission

from apps.accesscontrol.services import has_module_access, infer_admin_module


class HasRole(BasePermission):
    roles = set()

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if user.role not in self.roles:
            return False
        module = infer_admin_module(getattr(request, "path", ""), getattr(request, "method", "GET"))
        return has_module_access(user, module)


def role_permission(*roles):
    return type("RolePermission", (HasRole,), {"roles": set(roles)})
