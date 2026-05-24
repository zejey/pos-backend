"""Pricing resolution used by the POS when building a sale."""
from decimal import Decimal

from django.utils import timezone

from .models import Promo


def get_effective_price(product, on=None):
    """Return the price a customer pays now: active promo price, else list price."""
    on = on or timezone.localdate()
    promo = (
        Promo.objects.filter(product=product, is_active=True)
        .order_by("-start_date")
        .first()
    )
    if promo and promo.is_available(on):
        return Decimal(promo.promo_price)
    return Decimal(product.selling_price)
