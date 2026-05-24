from django.conf import settings
from django.db import models

from apps.catalog.models import Product


class StockMovement(models.Model):
    """Immutable ledger of every stock change.

    This is the single source of truth for the audit trail. Each row records
    a signed quantity (positive = stock in, negative = stock out) and the
    resulting balance, so inventory history is fully reconstructable. Records
    are never edited or deleted.
    """

    class Type(models.TextChoices):
        STOCK_IN = "STOCK_IN", "Stock In"
        SALE = "SALE", "Sale"
        SALE_REVERSAL = "SALE_REVERSAL", "Sale Reversal (Void)"
        ADJUSTMENT = "ADJUSTMENT", "Manual Adjustment"
        OPENING = "OPENING", "Opening Balance"

    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="movements"
    )
    movement_type = models.CharField(max_length=20, choices=Type.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)

    reference = models.CharField(max_length=64, blank=True)
    reason = models.CharField(max_length=255, blank=True)

    # Generic backlink to the originating record (Sale, StockIn, ...).
    source_type = models.CharField(max_length=40, blank=True)
    source_id = models.CharField(max_length=40, blank=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["product", "-created_at"]),
            models.Index(fields=["movement_type"]),
            models.Index(fields=["source_type", "source_id"]),
        ]

    def __str__(self):
        sign = "+" if self.quantity >= 0 else ""
        return f"{self.product.sku} {sign}{self.quantity} ({self.movement_type})"
