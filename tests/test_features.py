"""Module 03 (scoped): dashboard KPI (FEAT-12) and barcode lookup (FEAT-04)."""
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile

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


def test_product_create_defaults_reorder_level(admin_api):
    resp = admin_api.post(
        "/api/catalog/products/",
        {
            "name": "Default Reorder",
            "cost_price": "10.00",
            "selling_price": "15.00",
        },
        format="json",
    )
    assert resp.status_code == 201
    assert Decimal(str(resp.json()["reorder_level"])) == Decimal("5.00")


def test_inventory_movement_export_csv(make_product, admin_api):
    make_product(qty=Decimal("5"), name="Exported Item")

    resp = admin_api.get("/api/inventory/movements/export/")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    assert "attachment; filename=\"inventory-movements.csv\"" in resp["Content-Disposition"]
    body = resp.content.decode("utf-8")
    assert "product_sku" in body.splitlines()[0]
    assert "Exported Item" in body


def test_product_csv_import(make_product, admin_api):
    make_product(name="Existing Category Item")
    csv_data = (
        "name,sku,barcode,category,unit,cost_price,selling_price,reorder_level,is_active\n"
        "CSV Coffee,CSV-001,4800000000999,,pc,12.50,25.00,4,true\n"
        "CSV Tea,,4800000000888,,box,10.00,18.00,,true\n"
    )
    upload = SimpleUploadedFile("products.csv", csv_data.encode("utf-8"), content_type="text/csv")

    resp = admin_api.post(
        "/api/catalog/products/import-csv/",
        {"file": upload},
        format="multipart",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["created"] == 2
    assert any(item["sku"] == "CSV-001" for item in data["products"])


def test_stock_in_csv_import(make_product, admin_api):
    product_a = make_product(qty=0, name="Rice", sku="RICE-001")
    product_b = make_product(qty=0, name="Coffee", sku="COF-001")

    supplier_resp = admin_api.post(
        "/api/purchasing/suppliers/",
        {"name": "CSV Supplier"},
        format="json",
    )
    assert supplier_resp.status_code == 201
    supplier_id = supplier_resp.json()["id"]

    csv_data = (
        "reference_no,purchase_date,supplier,note,product,quantity_ordered,quantity_received,unit_cost,discrepancy_reason\n"
        f"PO-CSV-001,2026-06-30,{supplier_id},Monthly restock,{product_a.sku},10,10,30.50,\n"
        f"PO-CSV-001,2026-06-30,{supplier_id},Monthly restock,{product_b.sku},5,4,18.00,damaged pack\n"
    )
    upload = SimpleUploadedFile("stock-in.csv", csv_data.encode("utf-8"), content_type="text/csv")

    resp = admin_api.post(
        "/api/purchasing/stock-ins/import-csv/",
        {"file": upload},
        format="multipart",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["created"] == 1
    assert data["stock_ins"][0]["reference_no"] == "PO-CSV-001"
    assert len(data["stock_ins"][0]["items"]) == 2


def test_barcode_lookup(make_product, cashier_api):
    make_product(qty=Decimal("5"), barcode="4800123456789", name="Scanned")
    ok = cashier_api.get("/api/catalog/products/by-barcode/?barcode=4800123456789")
    assert ok.status_code == 200
    assert ok.json()["name"] == "Scanned"

    missing = cashier_api.get("/api/catalog/products/by-barcode/?barcode=0000")
    assert missing.status_code == 404

    blank = cashier_api.get("/api/catalog/products/by-barcode/")
    assert blank.status_code == 400
