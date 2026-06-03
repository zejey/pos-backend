"""Domain-level exceptions and a DRF exception handler that renders them.

These let the service layer raise business-rule violations (e.g. selling more
than is in stock) and have them returned as clean 400 responses.
"""
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class BusinessRuleError(Exception):
    """A business rule was violated (HTTP 400)."""

    default_message = "Business rule violation."

    def __init__(self, message=None, code="business_rule"):
        self.message = message or self.default_message
        self.code = code
        super().__init__(self.message)


class InsufficientStock(BusinessRuleError):
    """Attempted to deduct more stock than is available."""

    default_message = "Insufficient stock for the requested operation."

    def __init__(self, message=None):
        super().__init__(message, code="insufficient_stock")


def api_exception_handler(exc, context):
    """Render every handled error in one consistent envelope (FIX-06, FIX-09).

    Shape: ``{"detail": <human message>, "code": <machine code>[, "errors": {...}]}``
    - BusinessRuleError / InsufficientStock -> 400 with its code.
    - ProtectedError (deleting a record still referenced) -> friendly 400.
    - DRF errors -> wrapped in the same envelope; field-level validation
      messages are preserved under ``errors``.
    """
    if isinstance(exc, BusinessRuleError):
        return Response(
            {"detail": exc.message, "code": exc.code},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, ProtectedError):
        return Response(
            {
                "detail": "Cannot delete this record because other records "
                          "reference it (e.g. it has stock or sales history). "
                          "Deactivate it instead.",
                "code": "protected",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        return response

    code = getattr(exc, "default_code", "error")
    data = response.data
    if isinstance(data, dict) and set(data.keys()) == {"detail"}:
        # Already a simple {"detail": ...} (401/403/404/throttle/etc.).
        response.data = {"detail": data["detail"], "code": code}
    else:
        # Field-level validation errors (dict) or a list -> wrap consistently.
        response.data = {
            "detail": "Validation failed.",
            "code": "validation_error" if response.status_code == 400 else code,
            "errors": data,
        }
    return response
