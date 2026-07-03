"""Pricing resolution used by the POS when building a sale."""
from decimal import Decimal

from django.db.models import F, Q
from django.utils import timezone

from .models import Promo


def get_effective_price(product, on=None):
    """Return the price a customer pays now: active promo price, else list price."""
    on = on or timezone.localdate()
    promo = (
        Promo.objects.filter(product=product, is_active=True)
        .filter(Q(start_date__isnull=True) | Q(start_date__lte=on))
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=on))
        .order_by(F("start_date").desc(nulls_last=True), "-id")
        .first()
    )
    if promo:
        return Decimal(promo.promo_price)
    return Decimal(product.selling_price)


def get_active_promo(product, on=None):
    """Return the currently applicable promo row, if any."""
    on = on or timezone.localdate()
    return (
        Promo.objects.filter(product=product, is_active=True)
        .filter(Q(start_date__isnull=True) | Q(start_date__lte=on))
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=on))
        .order_by(F("start_date").desc(nulls_last=True), "-id")
        .first()
    )
