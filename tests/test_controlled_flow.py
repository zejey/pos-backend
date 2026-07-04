"""TEST-01 — Controlled-flow happy path: stock-in -> sale -> void -> adjust."""
from datetime import timedelta
from decimal import Decimal

import pytest
from model_bakery import baker

from apps.inventory.models import StockMovement
from apps.inventory.services import manual_adjustment
from apps.purchasing.services import post_stock_in
from apps.pricing.models import Discount, Promo
from apps.pricing.services import get_effective_price
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


def test_stock_in_discrepancy_is_logged_on_stock_movement(make_product):
    product = make_product(qty=0, cost=Decimal("10.00"))
    si = _stock_in(product, ordered="50", received="48", cost="12.50")
    item = si.items.first()
    item.discrepancy_reason = "2 items damaged on arrival"
    item.save(update_fields=["discrepancy_reason"])

    post_stock_in(si, user=None)

    mv = StockMovement.objects.get(product=product, movement_type="STOCK_IN")
    assert mv.quantity == Decimal("48.00")
    assert "ordered 50.00, received 48.00" in mv.reason
    assert "damaged" in mv.reason


def test_current_promo_beats_future_promo(make_product):
    from django.utils import timezone

    product = make_product(qty=Decimal("10"), price=Decimal("100.00"))
    today = timezone.localdate()
    Promo.objects.create(
        product=product,
        promo_price=Decimal("80.00"),
        start_date=today,
        is_active=True,
    )
    Promo.objects.create(
        product=product,
        promo_price=Decimal("50.00"),
        start_date=today + timedelta(days=7),
        is_active=True,
    )

    assert get_effective_price(product) == Decimal("80.00")


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


def test_fixed_discount_cannot_create_negative_sale_total(make_product):
    product = make_product(qty=Decimal("10"), price=Decimal("100.00"))
    discount = Discount.objects.create(
        name="Oversized coupon",
        discount_type=Discount.Type.FIXED,
        value=Decimal("250.00"),
        min_items_required=1,  # Override default to test capping behavior
        min_final_total_percent=Decimal("0.00"),  # Allow 100% discount for this test
    )
    sale = Sale.objects.create(tax_rate=current_tax_rate(), discount=discount)
    set_sale_items(sale, [{"product": product.pk, "quantity": Decimal("1")}])
    sale.refresh_from_db()

    assert sale.subtotal == Decimal("100.00")
    assert sale.discount_total == Decimal("100.00")
    assert sale.total == Decimal("0.00")


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


def test_admin_can_approve_item_void_request(make_product, cashier_api, admin_api):
    product = make_product(qty=Decimal("10"))
    sale = Sale.objects.create(tax_rate=current_tax_rate())
    set_sale_items(sale, [{"product": product.pk, "quantity": Decimal("3")}])
    sale_item = sale.items.first()

    resp = cashier_api.post(
        "/api/sales/item-void-requests/",
        {"sale_item": sale_item.pk, "quantity": "1", "reason": "wrong item scanned"},
        format="json",
    )
    assert resp.status_code == 201
    request_id = resp.data["id"]

    approve = admin_api.post(
        f"/api/sales/item-void-requests/{request_id}/approve/",
        {"password": "pass12345", "review_note": "approved"},
        format="json",
    )
    assert approve.status_code == 200

    sale.refresh_from_db()
    sale_item.refresh_from_db()
    assert sale.status == "DRAFT"
    assert sale_item.quantity == Decimal("2.00")
    assert sale_item.line_total == Decimal("200.00")


def test_admin_can_deny_item_void_request(make_product, cashier_api, admin_api):
    product = make_product(qty=Decimal("10"))
    sale = Sale.objects.create(tax_rate=current_tax_rate())
    set_sale_items(sale, [{"product": product.pk, "quantity": Decimal("2")}])
    sale_item = sale.items.first()

    resp = cashier_api.post(
        "/api/sales/item-void-requests/",
        {"sale_item": sale_item.pk, "reason": "customer changed mind"},
        format="json",
    )
    assert resp.status_code == 201
    request_id = resp.data["id"]

    deny = admin_api.post(
        f"/api/sales/item-void-requests/{request_id}/deny/",
        {"review_note": "keep item"},
        format="json",
    )
    assert deny.status_code == 200


def test_admin_must_confirm_password_to_approve_item_void(make_product, cashier_api, admin_api):
    product = make_product(qty=Decimal("10"))
    sale = Sale.objects.create(tax_rate=current_tax_rate())
    set_sale_items(sale, [{"product": product.pk, "quantity": Decimal("1")}])
    sale_item = sale.items.first()

    resp = cashier_api.post(
        "/api/sales/item-void-requests/",
        {"sale_item": sale_item.pk, "reason": "wrong item scanned"},
        format="json",
    )
    assert resp.status_code == 201
    request_id = resp.data["id"]

    approve = admin_api.post(
        f"/api/sales/item-void-requests/{request_id}/approve/",
        {"password": "wrong-password", "review_note": "approved"},
        format="json",
    )
    assert approve.status_code == 400
    assert "Admin password is incorrect." in approve.content.decode()

    sale.refresh_from_db()
    assert sale.items.count() == 1


def test_manual_adjustment_writes_movement_with_reason(make_product):
    product = make_product(qty=Decimal("20"))
    manual_adjustment(product=product, delta=Decimal("-2"), reason="damaged")
    product.refresh_from_db()

    assert product.quantity_on_hand == Decimal("18.00")
    mv = StockMovement.objects.get(movement_type="ADJUSTMENT")
    assert mv.quantity == Decimal("-2.00") and mv.reason == "damaged"
