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

from .models import Payment, Sale, SaleItem, SaleItemVoidRequest

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
    items = list(sale.items.all())
    subtotal = sum((i.line_total for i in items), Decimal("0.00"))
    discount_total = Decimal("0.00")
    if sale.discount and sale.discount.is_available():
        discount_total = sale.discount.compute(subtotal, item_count=len(items))
    sale.subtotal = money(subtotal)
    sale.discount_total = money(discount_total)
    sale.total = money(subtotal - discount_total)
    sale.tax_amount = vat_inclusive_tax(sale.total, sale.tax_rate)
    sale.save(update_fields=[
        "subtotal", "discount_total", "total", "tax_amount", "updated_at",
    ])
    return sale


def recalculate_sale(sale):
    """Public wrapper for API updates that change sale-level pricing fields."""
    return _recalculate(sale)


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


@transaction.atomic
def request_item_void(*, sale, sale_item_id, quantity, reason, user=None):
    """Create a cashier request to void one or more units from a draft item."""
    if sale.status != Sale.Status.DRAFT:
        raise BusinessRuleError("Only draft sales can have item void requests.")

    sale_item = sale.items.select_related("product").filter(pk=sale_item_id).first()
    if sale_item is None:
        raise BusinessRuleError("The selected sale item does not belong to this draft.")

    quantity = Decimal(quantity)
    if quantity <= 0:
        raise BusinessRuleError("Void quantity must be positive.")
    if quantity > sale_item.quantity:
        raise BusinessRuleError("Void quantity cannot exceed the scanned quantity.")

    if SaleItemVoidRequest.objects.filter(
        sale=sale,
        sale_item_id=sale_item_id,
        status=SaleItemVoidRequest.Status.PENDING,
    ).exists():
        raise BusinessRuleError("There is already a pending void request for this item.")

    return SaleItemVoidRequest.objects.create(
        sale=sale,
        sale_item_id=sale_item.pk,
        product_sku=sale_item.product.sku,
        product_name=sale_item.product.name,
        quantity=quantity,
        reason=reason,
        requested_by=user,
    )


def _apply_item_void_request(request_obj, reviewer, approved, review_note=""):
    with transaction.atomic():
        request_obj = SaleItemVoidRequest.objects.select_for_update().select_related("sale").get(
            pk=request_obj.pk
        )
        if request_obj.status != SaleItemVoidRequest.Status.PENDING:
            raise BusinessRuleError("This void request has already been reviewed.")

        request_obj.reviewed_by = reviewer
        request_obj.reviewed_at = timezone.now()
        request_obj.review_note = review_note or ""

        if not approved:
            request_obj.status = SaleItemVoidRequest.Status.DENIED
            request_obj.save(update_fields=[
                "status", "reviewed_by", "reviewed_at", "review_note", "updated_at",
            ])
            return request_obj

        sale = Sale.objects.select_for_update().get(pk=request_obj.sale_id)
        if sale.status != Sale.Status.DRAFT:
            raise BusinessRuleError("Only draft sales can have item void requests approved.")

        sale_item = sale.items.select_for_update().select_related("product").filter(
            pk=request_obj.sale_item_id
        ).first()
        if sale_item is None:
            raise BusinessRuleError("The requested sale item no longer exists.")
        if request_obj.quantity > sale_item.quantity:
            raise BusinessRuleError("The requested quantity is no longer available to void.")

        remaining = sale_item.quantity - request_obj.quantity
        if remaining > 0:
            sale_item.quantity = remaining
            sale_item.line_total = money(sale_item.unit_price * remaining)
            sale_item.save(update_fields=["quantity", "line_total"])
        else:
            sale_item.delete()

        sale = _recalculate(sale)

        request_obj.status = SaleItemVoidRequest.Status.APPROVED
        request_obj.save(update_fields=[
            "status", "reviewed_by", "reviewed_at", "review_note", "updated_at",
        ])
        return request_obj


def approve_item_void_request(request_obj, reviewer, review_note=""):
    """Approve an item void request and remove the item from the draft sale."""
    return _apply_item_void_request(request_obj, reviewer, approved=True, review_note=review_note)


def deny_item_void_request(request_obj, reviewer, review_note=""):
    """Deny an item void request."""
    return _apply_item_void_request(request_obj, reviewer, approved=False, review_note=review_note)
