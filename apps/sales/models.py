from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.catalog.models import Product
from apps.common.models import TimeStampedModel
from apps.pricing.models import Discount


class Sale(TimeStampedModel):
    """A POS transaction.

    Lifecycle: DRAFT (a cart) -> COMPLETED (paid, stock deducted) or VOID
    (reversed). Stock only moves on completion, through the inventory gateway.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        COMPLETED = "COMPLETED", "Completed"
        VOID = "VOID", "Void"

    receipt_no = models.CharField(
        max_length=32, unique=True, null=True, blank=True
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="sales",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    discount = models.ForeignKey(
        Discount, null=True, blank=True, on_delete=models.SET_NULL, related_name="sales"
    )

    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    discount_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    # VAT-inclusive: `total` already includes tax; `tax_amount` is the portion
    # carved out for the receipt. `tax_rate` (percent) is snapshotted at sale
    # creation so a later config change never rewrites historical receipts.
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    note = models.CharField(max_length=255, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["completed_at"]),
        ]

    def __str__(self):
        return self.receipt_no or f"Draft sale #{self.pk}"

    @property
    def amount_paid(self):
        return sum((p.amount for p in self.payments.all()), Decimal("0.00"))

    @property
    def change_due(self):
        change = self.amount_paid - self.total
        return change if change > 0 else Decimal("0.00")

    @property
    def net_of_tax(self):
        """VATable amount: the total minus the carved-out tax (POS standard)."""
        return (self.total - self.tax_amount).quantize(Decimal("0.01"))


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)  # snapshot
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    def __str__(self):
        return f"{self.product.sku} x{self.quantity}"


class Payment(models.Model):
    """Payment line. A sale may have several (split / mixed tender)."""

    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        GCASH = "GCASH", "GCash"
        MAYA = "MAYA", "Maya"
        CARD = "CARD", "Card"
        BANK = "BANK", "Bank Transfer"
        OTHER = "OTHER", "Other"

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="payments")
    method = models.CharField(max_length=10, choices=Method.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    tendered = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    reference = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return f"{self.method} {self.amount}"


class SaleItemVoidRequest(TimeStampedModel):
    """A cashier request to void a scanned item from a draft sale.

    This is a review workflow, not an inventory reversal. Stock only changes
    when the draft sale is later completed.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        DENIED = "DENIED", "Denied"

    sale = models.ForeignKey(
        Sale, on_delete=models.CASCADE, related_name="item_void_requests"
    )
    sale_item_id = models.PositiveBigIntegerField()
    product_sku = models.CharField(max_length=64)
    product_name = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sale_item_void_requests",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_sale_item_void_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["sale", "status"]),
        ]

    def __str__(self):
        return f"Item void request #{self.pk} ({self.status})"
