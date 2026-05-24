from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.catalog.models import Product
from apps.common.models import TimeStampedModel


class Discount(TimeStampedModel):
    """An order-level discount (Pricing 1.1): percentage or fixed amount."""

    class Type(models.TextChoices):
        PERCENTAGE = "PERCENTAGE", "Percentage"
        FIXED = "FIXED", "Fixed amount"

    name = models.CharField(max_length=80)
    discount_type = models.CharField(max_length=10, choices=Type.choices)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        unit = "%" if self.discount_type == self.Type.PERCENTAGE else ""
        return f"{self.name} ({self.value}{unit})"

    def is_available(self, on=None):
        on = on or timezone.localdate()
        if not self.is_active:
            return False
        if self.start_date and on < self.start_date:
            return False
        if self.end_date and on > self.end_date:
            return False
        return True

    def compute(self, base_amount):
        """Discount amount for a given base, never exceeding the base."""
        base_amount = Decimal(base_amount)
        if self.discount_type == self.Type.PERCENTAGE:
            amount = base_amount * (self.value / Decimal("100"))
        else:
            amount = self.value
        amount = min(amount, base_amount)
        return amount.quantize(Decimal("0.01"))


class Promo(TimeStampedModel):
    """A product-level promo price for a date window (Pricing 1.2)."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="promos"
    )
    promo_price = models.DecimalField(max_digits=12, decimal_places=2)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"Promo {self.product.sku} @ {self.promo_price}"

    def is_available(self, on=None):
        on = on or timezone.localdate()
        if not self.is_active:
            return False
        if self.start_date and on < self.start_date:
            return False
        if self.end_date and on > self.end_date:
            return False
        return True
