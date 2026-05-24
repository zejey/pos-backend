"""POS business logic: build cart, complete (deduct stock), void (reverse)."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Product
from apps.common.exceptions import BusinessRuleError
from apps.inventory.models import StockMovement
from apps.inventory.services import apply_movement
from apps.pricing.services import get_effective_price

from .models import Payment, Sale, SaleItem

CENTS = Decimal("0.01")


def _recalculate(sale):
    """Recompute subtotal/discount/total from the sale's current items."""
    subtotal = sum((i.line_total for i in sale.items.all()), Decimal("0.00"))
    discount_total = Decimal("0.00")
    if sale.discount and sale.discount.is_available():
        discount_total = sale.discount.compute(subtotal)
    sale.subtotal = subtotal.quantize(CENTS)
    sale.discount_total = discount_total
    sale.total = (subtotal - discount_total).quantize(CENTS)
    sale.save(update_fields=["subtotal", "discount_total", "total", "updated_at"])
    return sale


@transaction.atomic
def set_sale_items(sale, items):
    """Replace the cart contents. Prices are snapshotted at add time.

    `items` is a list of {"product": <pk or instance>, "quantity": Decimal}.
    """
    if sale.status != Sale.Status.DRAFT:
        raise BusinessRuleError("Only draft sales can be modified.")

    sale.items.all().delete()
    rows = []
    for entry in items:
        product = entry["product"]
        if not isinstance(product, Product):
            product = Product.objects.get(pk=product)
        quantity = Decimal(entry["quantity"])
        if quantity <= 0:
            raise BusinessRuleError("Item quantity must be positive.")
        unit_price = get_effective_price(product)
        line_total = (unit_price * quantity).quantize(CENTS)
        rows.append(SaleItem(
            sale=sale, product=product, quantity=quantity,
            unit_price=unit_price, line_total=line_total,
        ))
    SaleItem.objects.bulk_create(rows)
    return _recalculate(sale)


def _generate_receipt_no(sale):
    return f"R{timezone.now():%Y%m%d}-{sale.pk:06d}"


@transaction.atomic
def complete_sale(sale, payments, user=None):
    """Finalize a draft sale: validate payment, deduct stock, issue receipt.

    `payments` is a list of {"method", "amount", "tendered"?, "reference"?}.
    Stock is deducted atomically; if any line lacks stock the whole sale rolls
    back (InsufficientStock is raised).
    """
    if sale.status != Sale.Status.DRAFT:
        raise BusinessRuleError("Only draft sales can be completed.")

    sale = _recalculate(Sale.objects.select_for_update().get(pk=sale.pk))
    items = list(sale.items.select_related("product").all())
    if not items:
        raise BusinessRuleError("Cannot complete a sale with no items.")

    paid = sum((Decimal(p["amount"]) for p in payments), Decimal("0.00"))
    if paid < sale.total:
        raise BusinessRuleError(
            f"Insufficient payment: {paid} paid for a total of {sale.total}."
        )

    sale.receipt_no = _generate_receipt_no(sale)

    # Deduct stock through the controlled gateway (raises if not enough).
    for item in items:
        apply_movement(
            product=item.product_id,
            quantity=-item.quantity,
            movement_type=StockMovement.Type.SALE,
            user=user,
            reference=sale.receipt_no,
            source=sale,
        )

    Payment.objects.bulk_create([
        Payment(
            sale=sale,
            method=p["method"],
            amount=Decimal(p["amount"]),
            tendered=Decimal(p.get("tendered") or 0),
            reference=p.get("reference", ""),
        )
        for p in payments
    ])

    sale.status = Sale.Status.COMPLETED
    sale.completed_at = timezone.now()
    sale.save(update_fields=["status", "completed_at", "receipt_no", "updated_at"])
    return sale


@transaction.atomic
def void_sale(sale, reason, user=None):
    """Void a completed sale and return its items to stock."""
    if sale.status != Sale.Status.COMPLETED:
        raise BusinessRuleError("Only completed sales can be voided.")
    if not reason:
        raise BusinessRuleError("A reason is required to void a sale.")

    for item in sale.items.select_related("product").all():
        apply_movement(
            product=item.product_id,
            quantity=item.quantity,  # add back
            movement_type=StockMovement.Type.SALE_REVERSAL,
            user=user,
            reference=sale.receipt_no,
            reason=reason,
            source=sale,
        )

    sale.status = Sale.Status.VOID
    sale.voided_at = timezone.now()
    sale.void_reason = reason
    sale.save(update_fields=["status", "voided_at", "void_reason", "updated_at"])
    return sale
