from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.catalog.models import Product
from apps.common.models import TimeStampedModel


class StockIn(TimeStampedModel):
    """A purchase / stock-in document (the start of the controlled flow).

    Created as DRAFT, then POSTED. Posting is what updates inventory; a posted
    document is the permanent purchase record with its reference number.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        POSTED = "POSTED", "Posted"

    reference_no = models.CharField(
        max_length=64, unique=True,
        help_text="Supplier receipt / invoice number.",
    )
    supplier = models.CharField(max_length=160, blank=True)
    purchase_date = models.DateField()
    note = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="stock_ins",
    )
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-purchase_date", "-id"]

    def __str__(self):
        return f"Stock-In {self.reference_no} ({self.status})"

    @property
    def total_cost(self):
        return sum((item.line_cost for item in self.items.all()), Decimal("0.00"))


class StockInItem(models.Model):
    stock_in = models.ForeignKey(
        StockIn, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")
    quantity_ordered = models.DecimalField(max_digits=12, decimal_places=2)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    discrepancy_reason = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.product.sku} x{self.quantity_received}"

    @property
    def discrepancy_qty(self):
        return self.quantity_ordered - self.quantity_received

    @property
    def line_cost(self):
        return (self.quantity_received * self.unit_cost).quantize(Decimal("0.01"))
