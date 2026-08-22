from rest_framework.permissions import BasePermission
class HasRole(BasePermission):
    roles = set()
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.is_superuser or request.user.role in self.roles))

def role_permission(*roles):
    return type("RolePermission", (HasRole,), {"roles": set(roles)})
