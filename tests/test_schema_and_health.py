"""TEST-05 — Schema/contract + health endpoint (FIX-04)."""
import pytest

pytestmark = pytest.mark.django_db


def test_health_is_public_and_ok(api):
    resp = api.get("/api/health/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_openapi_schema_available(admin_api):
    assert admin_api.get("/api/schema/").status_code == 200


def test_sale_serializer_exposes_tax_fields(make_product, cashier_api):
    """Guard the frontend contract: tax fields must stay on the sale payload."""
    resp = cashier_api.post("/api/sales/sales/", {}, format="json")
    body = resp.json()
    for field in ("subtotal", "discount_total", "total", "tax_rate",
                  "tax_amount", "net_of_tax"):
        assert field in body, f"missing {field} on sale payload"
