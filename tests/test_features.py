"""Module 03 (scoped): dashboard KPI (FEAT-12) and barcode lookup (FEAT-04)."""
from decimal import Decimal

import pytest

from apps.sales.models import Sale
from apps.sales.services import complete_sale, current_tax_rate, set_sale_items

pytestmark = pytest.mark.django_db


def test_dashboard_bundles_kpis(make_product, admin_api):
    p = make_product(qty=Decimal("100"), price=Decimal("10.00"))
    low = make_product(qty=Decimal("1"), price=Decimal("5.00"))  # below reorder
    sale = Sale.objects.create(tax_rate=current_tax_rate())
    set_sale_items(sale, [{"product": p.pk, "quantity": Decimal("4")}])
    complete_sale(sale, [{"method": "CASH", "amount": "40.00", "tendered": "40.00"}])

    data = admin_api.get("/api/reports/dashboard/").json()
    assert data["today"]["transactions"] == 1
    assert Decimal(str(data["today"]["gross_sales"])) == Decimal("40.00")
    assert data["low_stock_count"] >= 1
    assert data["top_item"]["product"] == p.pk
    assert Decimal(str(data["top_item"]["quantity_sold"])) == Decimal("4.00")


def test_barcode_lookup(make_product, cashier_api):
    make_product(qty=Decimal("5"), barcode="4800123456789", name="Scanned")
    ok = cashier_api.get("/api/catalog/products/by-barcode/?barcode=4800123456789")
    assert ok.status_code == 200
    assert ok.json()["name"] == "Scanned"

    missing = cashier_api.get("/api/catalog/products/by-barcode/?barcode=0000")
    assert missing.status_code == 404

    blank = cashier_api.get("/api/catalog/products/by-barcode/")
    assert blank.status_code == 400
