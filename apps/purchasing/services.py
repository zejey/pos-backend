"""Posting a stock-in document updates inventory through the controlled gateway."""
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Product
from apps.common.exceptions import BusinessRuleError
from apps.inventory.models import StockMovement
from apps.inventory.services import apply_movement

from .models import StockIn


@transaction.atomic
def post_stock_in(stock_in, user=None):
    """Commit a DRAFT stock-in: add received quantities to inventory.

    - Only received quantities enter stock (discrepancies are excluded).
    - Each line writes a STOCK_IN movement referencing the document.
    - Product cost price is refreshed to the latest purchase cost so profit
      estimation stays meaningful.
    """
    if stock_in.status == StockIn.Status.POSTED:
        raise BusinessRuleError("This stock-in has already been posted.")

    items = list(stock_in.items.select_related("product").all())
    if not items:
        raise BusinessRuleError("Cannot post a stock-in with no items.")

    for item in items:
        if item.quantity_received <= 0:
            continue
        reason = ""
        if item.discrepancy_qty:
            reason = (
                f"Stock-in discrepancy: ordered {item.quantity_ordered}, "
                f"received {item.quantity_received}. {item.discrepancy_reason}"
            ).strip()
        apply_movement(
            product=item.product_id,
            quantity=item.quantity_received,
            movement_type=StockMovement.Type.STOCK_IN,
            user=user,
            reference=stock_in.reference_no,
            reason=reason,
            source=stock_in,
        )
        # Refresh latest cost for profit estimation.
        Product.objects.filter(pk=item.product_id).update(cost_price=item.unit_cost)

    stock_in.status = StockIn.Status.POSTED
    stock_in.posted_at = timezone.now()
    stock_in.save(update_fields=["status", "posted_at", "updated_at"])
    return stock_in
