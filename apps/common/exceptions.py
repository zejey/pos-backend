"""Domain-level exceptions and a DRF exception handler that renders them.

These let the service layer raise business-rule violations (e.g. selling more
than is in stock) and have them returned as clean 400 responses.
"""
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
    """Render BusinessRuleError as a structured 400; defer otherwise to DRF."""
    if isinstance(exc, BusinessRuleError):
        return Response(
            {"detail": exc.message, "code": exc.code},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return drf_exception_handler(exc, context)
