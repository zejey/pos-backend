"""TEST-04 — Reports correctness against known seeded data."""
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
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

class TestInventoryTurnoverReport:
    """Test the InventoryTurnoverReport endpoint."""
    
    def test_turnover_report_basic(self, make_product, admin_api):
        """Test turnover report returns data with correct structure."""
        product = make_product(
            qty=Decimal("100"),
            price=Decimal("50.00"),
            cost=Decimal("30.00")  # Use 'cost' not 'cost_price'
        )
        sale = Sale.objects.create(tax_rate=current_tax_rate())
        set_sale_items(sale, [{"product": product.pk, "quantity": Decimal("10")}])
        complete_sale(sale, [{"method": "CASH", "amount": "500.00", "tendered": "500.00"}])
        
        today = timezone.localdate()
        resp = admin_api.get(
            f"/api/reports/inventory-turnover/?start={today}&end={today}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "summary" in data
        assert data["summary"]["overall_turnover_rate"] is not None
    
    def test_turnover_report_pagination_limit(self, make_product, admin_api):
        """Test turnover report respects limit parameter."""
        for i in range(10):
            product = make_product(
                qty=Decimal("100"),
                price=Decimal("50.00"),
                cost=Decimal("30.00")  # Use 'cost' not 'cost_price'
            )
            sale = Sale.objects.create(tax_rate=current_tax_rate())
            set_sale_items(sale, [{"product": product.pk, "quantity": Decimal("1")}])
            complete_sale(sale, [{"method": "CASH", "amount": "50.00", "tendered": "50.00"}])
        
        today = timezone.localdate()
        resp = admin_api.get(
            f"/api/reports/inventory-turnover/?start={today}&end={today}&limit=5"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 5


class TestReorderPointReport:
    """Test the ReorderPointReport endpoint."""
    
    def test_reorder_point_basic(self, make_product, admin_api):
        """Test reorder point report returns data with correct structure."""
        product = make_product(
            qty=Decimal("5"),
            price=Decimal("50.00")
            # reorder_level already defaults to Decimal("5.00") in fixture
        )
        sale = Sale.objects.create(tax_rate=current_tax_rate())
        set_sale_items(sale, [{"product": product.pk, "quantity": Decimal("2")}])
        complete_sale(sale, [{"method": "CASH", "amount": "100.00", "tendered": "100.00"}])
        
        resp = admin_api.get("/api/reports/reorder-point/")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "lookback_days" in data
        assert data["lookback_days"] == 30  # default
    
    def test_reorder_point_custom_params(self, make_product, admin_api):
        """Test reorder point with custom parameters."""
        product = make_product(qty=Decimal("50"))
        
        resp = admin_api.get(
            "/api/reports/reorder-point/?days=7&lead_time_days=14&safety_factor=0.75"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["lookback_days"] == 7
        assert data["lead_time_days"] == 14
        assert data["safety_factor"] == 0.75
    
    def test_reorder_point_low_stock_only(self, make_product, admin_api):
        """Test reorder point filtered for low stock only."""
        product = make_product(qty=Decimal("5"))
        # Product already has reorder_level = 5, so qty=5 will trigger needs_reorder
        
        resp = admin_api.get("/api/reports/reorder-point/?low_stock_only=true")
        assert resp.status_code == 200
        data = resp.json()
        # All returned products should need reorder
        for result in data["results"]:
            assert result["needs_reorder"] is True