from decimal import Decimal
from nanoid import generate
from django.db import models

from apps.common.models import TimeStampedModel

SKU_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

def generate_sku():
    while True:
        sku = f"SKU-{generate(SKU_ALPHABET, 12)}"
        if not Product.objects.filter(sku=sku).exists():
            return sku
        
class Category(TimeStampedModel):
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=255, blank=True)  
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    """A sellable item.

    `quantity_on_hand` is a cached running balance. It is NEVER written
    directly by the API — it changes only through apps.inventory.services so
    every movement leaves a StockMovement record (controlled flow / audit
    trail requirement).
    """

    sku = models.CharField(
        max_length=20,
        unique=True,
        default=generate_sku,
        editable=False,
    )
    barcode = models.CharField(max_length=64, blank=True, db_index=True)
    name = models.CharField(max_length=160)
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
    )
    unit = models.CharField(max_length=20, default="pc")

    cost_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    selling_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    quantity_on_hand = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"), editable=False
    )
    reorder_level = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name"]), models.Index(fields=["sku"])]

    def __str__(self):
        return f"{self.name} [{self.sku}]"

    @property
    def is_low_stock(self):
        return self.quantity_on_hand <= self.reorder_level

    @property
    def stock_value(self):
        """Inventory value at cost."""
        return (self.quantity_on_hand * self.cost_price).quantize(Decimal("0.01"))
