"""Shared helpers for activity logging, importable by every module."""
from .models import ActivityLog


def get_client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_activity(user, action, *, entity="", entity_id="", detail=None, request=None):
    """Write a single audit-trail entry.

    Call this from any module after a meaningful action (sale, stock-in,
    adjustment, login). Never raises on bad input so logging cannot break a
    business transaction.
    """
    try:
        return ActivityLog.objects.create(
            user=user if (user and user.is_authenticated) else None,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id else "",
            detail=detail or {},
            ip_address=get_client_ip(request),
        )
    except Exception:  # pragma: no cover - logging must never crash a request
        return None
