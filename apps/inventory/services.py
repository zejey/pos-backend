"""The controlled stock gateway.

Every change to a product's quantity_on_hand MUST go through apply_movement().
It locks the product row, updates the cached balance, and writes an immutable
StockMovement in the same transaction. This is what guarantees the brief's
rule: "no direct editing of stock without record. All movements traceable."
"""
from decimal import Decimal

from django.db import transaction

from apps.catalog.models import Product
from apps.common.exceptions import BusinessRuleError, InsufficientStock

from .models import StockMovement


@transaction.atomic
def apply_movement(
    *,
    product,
    quantity,
    movement_type,
    user=None,
    reference="",
    reason="",
    source=None,
    allow_negative=False,
):
    """Apply a signed stock change and record it.

    Args:
        product: Product instance (or pk) to move.
        quantity: signed Decimal. Positive adds stock, negative removes it.
        movement_type: one of StockMovement.Type.
        allow_negative: permit the balance to go below zero (default False).

    Returns the created StockMovement. Raises InsufficientStock when a
    deduction would drive the balance negative.
    """
    quantity = Decimal(quantity)
    if quantity == 0:
        raise BusinessRuleError("Movement quantity cannot be zero.")

    pk = product.pk if isinstance(product, Product) else product
    locked = Product.objects.select_for_update().get(pk=pk)

    new_balance = locked.quantity_on_hand + quantity
    if new_balance < 0 and not allow_negative:
        raise InsufficientStock(
            f"Cannot deduct {abs(quantity)} of {locked.sku}; "
            f"only {locked.quantity_on_hand} on hand."
        )

    locked.quantity_on_hand = new_balance
    locked.save(update_fields=["quantity_on_hand", "updated_at"])

    return StockMovement.objects.create(
        product=locked,
        movement_type=movement_type,
        quantity=quantity,
        balance_after=new_balance,
        reference=reference,
        reason=reason,
        source_type=source.__class__.__name__ if source is not None else "",
        source_id=str(source.pk) if source is not None else "",
        user=user,
    )


def manual_adjustment(*, product, new_quantity=None, delta=None, reason, user=None):
    """Manual stock adjustment with mandatory reason (Inventory 1.5).

    Provide either an absolute `new_quantity` (e.g. after a physical count) or
    a signed `delta` (e.g. -2 for damaged items). The reason is required and is
    stored on the movement for the audit trail.
    """
    if not reason:
        raise BusinessRuleError("A reason is required for manual adjustments.")
    if (new_quantity is None) == (delta is None):
        raise BusinessRuleError("Provide exactly one of new_quantity or delta.")

    pk = product.pk if isinstance(product, Product) else product
    with transaction.atomic():
        current = Product.objects.select_for_update().get(pk=pk).quantity_on_hand
        change = (Decimal(new_quantity) - current) if new_quantity is not None else Decimal(delta)
        if change == 0:
            raise BusinessRuleError("Adjustment results in no change.")
        return apply_movement(
            product=pk,
            quantity=change,
            movement_type=StockMovement.Type.ADJUSTMENT,
            reason=reason,
            user=user,
            allow_negative=True,  # corrections may legitimately set any count
        )
    
def set_opening_stock(*, product, quantity, reason="Opening stock", user=None):
    """Record the starting balance for a newly created product.

    Used when a product is created with a non-zero initial count (manual
    add-product form or Excel import). This is not a correction to an
    existing balance, so it always logs as OPENING rather than ADJUSTMENT.
    """
    quantity = Decimal(quantity)
    if quantity <= 0:
        raise BusinessRuleError("Opening stock must be a positive quantity.")

    return apply_movement(
        product=product,
        quantity=quantity,
        movement_type=StockMovement.Type.STOCK_IN,
        reason=reason,
        user=user,
    )
