"""TEST-01 — Controlled-flow happy path: stock-in -> sale -> void -> adjust."""
from decimal import Decimal

import pytest
from model_bakery import baker

from apps.inventory.models import StockMovement
from apps.inventory.services import manual_adjustment
from apps.purchasing.services import post_stock_in
from apps.sales.models import Sale
from apps.sales.services import complete_sale, current_tax_rate, set_sale_items

pytestmark = pytest.mark.django_db


def _stock_in(product, ordered, received, cost):
    from apps.purchasing.models import StockIn, StockInItem
    si = baker.make("purchasing.StockIn", status=StockIn.Status.DRAFT)
    StockInItem.objects.create(
        stock_in=si, product=product,
        quantity_ordered=Decimal(ordered), quantity_received=Decimal(received),
        unit_cost=Decimal(cost),
    )
    return si


def test_posting_stock_in_raises_quantity_and_refreshes_cost(make_product):
    product = make_product(qty=0, cost=Decimal("10.00"))
    si = _stock_in(product, ordered="50", received="50", cost="12.50")

    post_stock_in(si, user=None)
    product.refresh_from_db()
    si.refresh_from_db()

    assert product.quantity_on_hand == Decimal("50.00")
    assert product.cost_price == Decimal("12.50")  # cost refreshed to latest
    assert si.status == "POSTED" and si.posted_at is not None
    mv = StockMovement.objects.get(product=product, movement_type="STOCK_IN")
    assert mv.quantity == Decimal("50.00") and mv.balance_after == Decimal("50.00")


def test_completed_sale_deducts_stock_and_records_movement(make_product):
    product = make_product(qty=Decimal("100"), price=Decimal("50.00"))
    sale = Sale.objects.create(tax_rate=current_tax_rate())
    set_sale_items(sale, [{"product": product.pk, "quantity": Decimal("3")}])

    sale = complete_sale(
        sale, [{"method": "CASH", "amount": "200.00", "tendered": "200.00"}]
    )
    product.refresh_from_db()

    assert sale.status == "COMPLETED"
    assert sale.receipt_no  # generated
    assert sale.change_due == Decimal("50.00")  # paid 200 for a 150 total
    assert product.quantity_on_hand == Decimal("97.00")
    mv = StockMovement.objects.get(source_type="Sale", source_id=str(sale.pk))
    assert mv.movement_type == "SALE" and mv.quantity == Decimal("-3.00")


def test_void_returns_stock_and_writes_reversal(make_product):
    product = make_product(qty=Decimal("10"))
    sale = Sale.objects.create(tax_rate=current_tax_rate())
    set_sale_items(sale, [{"product": product.pk, "quantity": Decimal("4")}])
    sale = complete_sale(sale, [{"method": "CASH", "amount": "400.00", "tendered": "400.00"}])

    from apps.sales.services import void_sale
    void_sale(sale, reason="customer changed mind")
    product.refresh_from_db()

    assert sale.status == "VOID"
    assert product.quantity_on_hand == Decimal("10.00")  # back to start
    rev = StockMovement.objects.get(movement_type="SALE_REVERSAL")
    assert rev.quantity == Decimal("4.00") and rev.reason == "customer changed mind"


def test_manual_adjustment_writes_movement_with_reason(make_product):
    product = make_product(qty=Decimal("20"))
    manual_adjustment(product=product, delta=Decimal("-2"), reason="damaged")
    product.refresh_from_db()

    assert product.quantity_on_hand == Decimal("18.00")
    mv = StockMovement.objects.get(movement_type="ADJUSTMENT")
    assert mv.quantity == Decimal("-2.00") and mv.reason == "damaged"
