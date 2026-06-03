"""TEST-02 — Edge cases & failures, including the FIX-01/FIX-02 guards."""
from decimal import Decimal

import pytest
from model_bakery import baker

from apps.common.exceptions import BusinessRuleError, InsufficientStock
from apps.purchasing.models import StockIn, StockInItem
from apps.purchasing.services import post_stock_in
from apps.sales.models import Payment, Sale
from apps.sales.services import complete_sale, current_tax_rate, set_sale_items, void_sale

pytestmark = pytest.mark.django_db


def _draft_with(product, qty):
    sale = Sale.objects.create(tax_rate=current_tax_rate())
    set_sale_items(sale, [{"product": product.pk, "quantity": Decimal(qty)}])
    return sale


def test_oversell_rolls_back_entire_sale(make_product):
    product = make_product(qty=Decimal("2"))
    sale = _draft_with(product, "5")  # more than on hand

    with pytest.raises(InsufficientStock):
        complete_sale(sale, [{"method": "CASH", "amount": "500.00", "tendered": "500.00"}])

    sale.refresh_from_db()
    product.refresh_from_db()
    assert sale.status == "DRAFT"               # not completed
    assert product.quantity_on_hand == Decimal("2.00")  # nothing deducted
    assert Payment.objects.filter(sale=sale).count() == 0  # no orphan payments


def test_cannot_complete_twice(make_product):
    product = make_product(qty=Decimal("10"))
    sale = _draft_with(product, "1")
    complete_sale(sale, [{"method": "CASH", "amount": "100.00", "tendered": "100.00"}])
    with pytest.raises(BusinessRuleError):
        complete_sale(sale, [{"method": "CASH", "amount": "100.00", "tendered": "100.00"}])


def test_cannot_post_stock_in_twice(make_product):
    product = make_product(qty=0)
    si = baker.make(StockIn, status=StockIn.Status.DRAFT)
    StockInItem.objects.create(
        stock_in=si, product=product, quantity_ordered=Decimal("5"),
        quantity_received=Decimal("5"), unit_cost=Decimal("1"),
    )
    post_stock_in(si)
    with pytest.raises(BusinessRuleError):
        post_stock_in(si)


def test_cannot_void_a_draft(make_product):
    product = make_product(qty=Decimal("5"))
    sale = _draft_with(product, "1")
    with pytest.raises(BusinessRuleError):
        void_sale(sale, reason="nope")


def test_adjustment_requires_reason(make_product):
    from apps.inventory.services import manual_adjustment
    product = make_product(qty=Decimal("5"))
    with pytest.raises(BusinessRuleError):
        manual_adjustment(product=product, delta=Decimal("-1"), reason="")


def test_inactive_product_cannot_be_carted(make_product):
    product = make_product(qty=Decimal("5"), active=False)
    sale = Sale.objects.create(tax_rate=current_tax_rate())
    with pytest.raises(BusinessRuleError):
        set_sale_items(sale, [{"product": product.pk, "quantity": Decimal("1")}])


def test_payment_below_total_rejected_via_api(make_product, cashier_api):
    product = make_product(qty=Decimal("10"), price=Decimal("100.00"))
    sale = _draft_with(product, "2")  # total 200
    resp = cashier_api.post(
        f"/api/sales/sales/{sale.pk}/complete/",
        {"payments": [{"method": "CASH", "amount": "50.00", "tendered": "50.00"}]},
        format="json",
    )
    assert resp.status_code == 400


def test_negative_payment_rejected_via_api(make_product, cashier_api):
    product = make_product(qty=Decimal("10"), price=Decimal("100.00"))
    sale = _draft_with(product, "1")
    resp = cashier_api.post(
        f"/api/sales/sales/{sale.pk}/complete/",
        {"payments": [{"method": "CASH", "amount": "-100.00", "tendered": "0.00"}]},
        format="json",
    )
    assert resp.status_code == 400


def test_cash_tender_below_amount_rejected_via_api(make_product, cashier_api):
    product = make_product(qty=Decimal("10"), price=Decimal("100.00"))
    sale = _draft_with(product, "1")
    resp = cashier_api.post(
        f"/api/sales/sales/{sale.pk}/complete/",
        {"payments": [{"method": "CASH", "amount": "100.00", "tendered": "50.00"}]},
        format="json",
    )
    assert resp.status_code == 400


def test_stock_in_discrepancy_requires_reason_via_api(make_product, admin_api):
    product = make_product(qty=0)
    resp = admin_api.post(
        "/api/purchasing/stock-ins/",
        {
            "reference_no": "INV-X1", "purchase_date": "2026-01-01",
            "items": [{
                "product": product.pk, "quantity_ordered": "10",
                "quantity_received": "8", "unit_cost": "5",
            }],
        },
        format="json",
    )
    assert resp.status_code == 400  # received != ordered, no discrepancy_reason
