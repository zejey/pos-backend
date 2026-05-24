"""Role-based permissions for the two roles in the brief: Admin and Cashier."""
from rest_framework.permissions import SAFE_METHODS, BasePermission


def _is_admin(user):
    return bool(user and user.is_authenticated and getattr(user, "is_admin", False))


class IsAdmin(BasePermission):
    """Only Admin users."""

    def has_permission(self, request, view):
        return _is_admin(request.user)


class IsAdminOrReadOnly(BasePermission):
    """Everyone authenticated can read; only Admin can write.

    Used for master data (products, discounts) which cashiers consult but
    must not modify.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return _is_admin(request.user)
