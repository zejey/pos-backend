"""TEST-04 — Reports correctness against known seeded data."""
from decimal import Decimal

import pytest

from apps.sales.models import Sale
from apps.sales.services import complete_sale, current_tax_rate, set_sale_items

pytestmark = pytest.mark.django_db


def _sell(product, qty, price_each):
    sale = Sale.objects.create(tax_rate=current_tax_rate())
    set_sale_items(sale, [{"product": product.pk, "quantity": Decimal(qty)}])
    total = (Decimal(qty) * Decimal(price_each)).quantize(Decimal("0.01"))
    return complete_sale(
        sale, [{"method": "CASH", "amount": str(total), "tendered": str(total)}]
    )


def test_sales_summary_and_profit(make_product, admin_api):
    # 5 units sold @ 100 (cost 60): revenue 500, COGS 300, profit 200.
    product = make_product(qty=Decimal("100"), price=Decimal("100.00"), cost=Decimal("60.00"))
    _sell(product, "2", "100.00")
    _sell(product, "3", "100.00")

    summary = admin_api.get("/api/reports/sales-summary/?period=daily").json()
    assert summary["transactions"] == 2
    assert Decimal(str(summary["gross_sales"])) == Decimal("500.00")
    # VAT-inclusive 12% carved out of 500 -> 53.57
    assert Decimal(str(summary["total_tax"])) == Decimal("53.57")

    profit = admin_api.get("/api/reports/profit-estimate/").json()
    assert Decimal(str(profit["revenue"])) == Decimal("500.00")
    assert Decimal(str(profit["estimated_cogs"])) == Decimal("300.00")
    assert Decimal(str(profit["estimated_profit"])) == Decimal("200.00")


def test_top_products_ordered_by_quantity(make_product, admin_api):
    a = make_product(qty=Decimal("100"), price=Decimal("10.00"), name="Apple")
    b = make_product(qty=Decimal("100"), price=Decimal("10.00"), name="Banana")
    _sell(a, "2", "10.00")
    _sell(b, "9", "10.00")

    rows = admin_api.get("/api/reports/top-products/").json()["results"]
    assert rows[0]["product"] == b.pk      # most units first
    assert Decimal(str(rows[0]["quantity_sold"])) == Decimal("9.00")


def test_inventory_status_totals_and_pagination(make_product, admin_api):
    make_product(qty=Decimal("10"), cost=Decimal("5.00"))   # value 50
    make_product(qty=Decimal("2"), cost=Decimal("5.00"))    # value 10, low stock

    data = admin_api.get("/api/reports/inventory-status/").json()
    assert data["product_count"] == 2
    assert Decimal(str(data["total_stock_value"])) == Decimal("60.00")
    assert data["low_stock_count"] == 1
    assert "results" in data and "count" in data  # paginated envelope
