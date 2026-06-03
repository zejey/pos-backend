"""Money helpers (FIX-10).

A single place that defines how monetary/decimal values are rounded, so totals
are consistently quantized to 2 decimal places with banker-free half-up rounding.
"""
from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")


def money(value):
    """Quantize a value to 2 decimal places (ROUND_HALF_UP)."""
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)
