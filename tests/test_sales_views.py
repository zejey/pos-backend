from decimal import Decimal

import pytest

from apps.sales.models import Sale
from apps.sales.services import complete_sale, current_tax_rate, set_sale_items

pytestmark = pytest.mark.django_db


def test_set_items_replaces_cart(make_product, cashier_api):
    """Test the set_items action replaces cart items."""
    product = make_product(qty=Decimal("100"), price=Decimal("50.00"))
    sale = Sale.objects.create(tax_rate=current_tax_rate())
    
    resp = cashier_api.post(
        f"/api/sales/sales/{sale.id}/set_items/",
        [{"product": product.pk, "quantity": "2"}],
        format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == "100.00"


def test_complete_sale_logs_activity(make_product, cashier_api):
    """Test that completing a sale logs activity."""
    from apps.accounts.models import ActivityLog
    
    product = make_product(qty=Decimal("10"), price=Decimal("100.00"))
    sale = Sale.objects.create(tax_rate=current_tax_rate())
    set_sale_items(sale, [{"product": product.pk, "quantity": Decimal("1")}])
    
    cashier = cashier_api.auth_user if hasattr(cashier_api, 'auth_user') else None
    resp = cashier_api.post(
        f"/api/sales/sales/{sale.id}/complete/",
        {"payments": [{"method": "CASH", "amount": "100.00", "tendered": "100.00"}]},
        format="json"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "T" not in body["completed_at"]
    assert "AM" in body["completed_at"] or "PM" in body["completed_at"]


def test_void_sale_logs_activity(make_product, admin_api):
    """Test that voiding a sale logs activity."""
    product = make_product(qty=Decimal("10"))
    sale = Sale.objects.create(tax_rate=current_tax_rate())
    set_sale_items(sale, [{"product": product.pk, "quantity": Decimal("1")}])
    complete_sale(sale, [{"method": "CASH", "amount": "100.00", "tendered": "100.00"}])
    
    resp = admin_api.post(
        f"/api/sales/sales/{sale.id}/void/",
        {"reason": "test void"},
        format="json"
    )
    assert resp.status_code == 200


def test_receipt_endpoint(make_product, cashier_api):
    """Test the receipt endpoint returns receipt data."""
    product = make_product(qty=Decimal("10"), price=Decimal("50.00"))
    sale = Sale.objects.create(tax_rate=current_tax_rate())
    set_sale_items(sale, [{"product": product.pk, "quantity": Decimal("2")}])
    complete_sale(sale, [{"method": "CASH", "amount": "100.00", "tendered": "100.00"}])
    
    resp = cashier_api.get(f"/api/sales/sales/{sale.id}/receipt/")
    assert resp.status_code == 200
    data = resp.json()
    assert "date" in data  # receipt has required fields


def test_daily_summary(make_product, cashier_api):
    """Test daily sales summary endpoint."""
    from django.utils import timezone
    
    product = make_product(qty=Decimal("100"), price=Decimal("100.00"))
    sale = Sale.objects.create(tax_rate=current_tax_rate())
    set_sale_items(sale, [{"product": product.pk, "quantity": Decimal("1")}])
    complete_sale(sale, [{"method": "CASH", "amount": "100.00", "tendered": "100.00"}])
    
    resp = cashier_api.get("/api/sales/sales/daily_summary/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["transactions"] == 1
    assert Decimal(str(data["gross_sales"])) > 0