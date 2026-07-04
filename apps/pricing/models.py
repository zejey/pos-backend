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
    
    # Business rule constraints
    minimum_purchase = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        help_text="Minimum subtotal required for this discount to apply."
    )
    max_discount_cap = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Maximum discount amount allowed (even if % calculates higher)."
    )
    min_items_required = models.PositiveIntegerField(
        default=2,
        help_text="Minimum number of items in cart to qualify for this discount."
    )
    min_final_total_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("10.00"),
        help_text="Minimum final total as % of subtotal (e.g., 10 = can't discount more than 90%). 0 = no limit."
    )

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

    def compute(self, base_amount, item_count=1):
        """Discount amount for a given base, with business rule constraints.
        
        Args:
            base_amount: The subtotal to apply discount to.
            item_count: Number of items in cart (for min_items_required check).
            
        Returns:
            Decimal discount amount, or Decimal("0.00") if conditions not met.
        """
        base_amount = Decimal(base_amount)
        
        # Check minimum purchase requirement
        if base_amount < self.minimum_purchase:
            return Decimal("0.00")
        
        # Check minimum items requirement
        if item_count < self.min_items_required:
            return Decimal("0.00")
        
        # Calculate discount amount
        if self.discount_type == self.Type.PERCENTAGE:
            amount = base_amount * (self.value / Decimal("100"))
        else:
            amount = self.value
        
        # Cap at base amount (never discount more than 100%)
        amount = min(amount, base_amount)
        
        # Apply max discount cap if set
        if self.max_discount_cap is not None:
            amount = min(amount, self.max_discount_cap)
        
        # Enforce minimum final total percentage
        if self.min_final_total_percent > 0:
            min_final = base_amount * (self.min_final_total_percent / Decimal("100"))
            max_allowed_discount = base_amount - min_final
            amount = min(amount, max_allowed_discount)
        
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
