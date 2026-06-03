"""POS business logic: build cart, complete (deduct stock), void (reverse)."""
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Product
from apps.common.exceptions import BusinessRuleError
from apps.common.money import money
from apps.inventory.models import StockMovement
from apps.inventory.services import apply_movement
from apps.pricing.services import get_effective_price

from .models import Payment, Sale, SaleItem

HUNDRED = Decimal("100")


def current_tax_rate():
    """The configured VAT rate (percent) snapshotted onto new sales."""
    return Decimal(settings.POS_TAX_RATE)


def vat_inclusive_tax(gross, rate):
    """VAT portion carved out of a tax-inclusive `gross` amount.

    For a gross that already includes `rate`% VAT: tax = gross * rate / (100 + rate).
    """
    if rate <= 0:
        return Decimal("0.00")
    return money(gross * rate / (HUNDRED + rate))


def _recalculate(sale):
    """Recompute subtotal/discount/total (and carved-out VAT) from the items."""
    subtotal = sum((i.line_total for i in sale.items.all()), Decimal("0.00"))
    discount_total = Decimal("0.00")
    if sale.discount and sale.discount.is_available():
        discount_total = sale.discount.compute(subtotal)
    sale.subtotal = money(subtotal)
    sale.discount_total = money(discount_total)
    sale.total = money(subtotal - discount_total)
    sale.tax_amount = vat_inclusive_tax(sale.total, sale.tax_rate)
    sale.save(update_fields=[
        "subtotal", "discount_total", "total", "tax_amount", "updated_at",
    ])
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
        if not product.is_active:
            raise BusinessRuleError(f"Product {product.sku} is not active for sale.")
        unit_price = get_effective_price(product)
        if unit_price <= 0:
            raise BusinessRuleError(
                f"Product {product.sku} has no sellable price."
            )
        line_total = money(unit_price * quantity)
        rows.append(SaleItem(
            sale=sale, product=product, quantity=quantity,
            unit_price=unit_price, line_total=line_total,
        ))
    SaleItem.objects.bulk_create(rows)
    return _recalculate(sale)


def _generate_receipt_no(sale):
    """Build the receipt number: ``{PREFIX}{YYYYMMDD}-{id:06d}``.

    Concurrency-safe by construction: the sale's primary key is assigned by the
    database and is globally unique, so two cashiers completing sales at the
    same instant can never collide. The store prefix is configurable via
    ``POS_RECEIPT_PREFIX``.
    """
    prefix = settings.POS_RECEIPT_PREFIX
    return f"{prefix}{timezone.now():%Y%m%d}-{sale.pk:06d}"


@transaction.atomic
def complete_sale(sale, payments, user=None):
    """Finalize a draft sale: validate payment, deduct stock, issue receipt.

    `payments` is a list of {"method", "amount", "tendered"?, "reference"?}.
    Stock is deducted atomically; if any line lacks stock the whole sale rolls
    back (InsufficientStock is raised).
    """
    # Lock the row first, then check status against the persisted state — this
    # is robust even if the caller passes a stale in-memory object.
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.status != Sale.Status.DRAFT:
        raise BusinessRuleError("Only draft sales can be completed.")

    sale = _recalculate(sale)
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
