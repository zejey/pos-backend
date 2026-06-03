"""TEST-03 — Role permission matrix (Admin vs Cashier vs anonymous)."""
import pytest

pytestmark = pytest.mark.django_db


def test_anonymous_is_rejected(api):
    assert api.get("/api/sales/sales/").status_code == 401
    assert api.get("/api/catalog/products/").status_code == 401


def test_cashier_can_read_products_and_create_sales(cashier_api):
    assert cashier_api.get("/api/catalog/products/").status_code == 200
    assert cashier_api.post("/api/sales/sales/", {}, format="json").status_code == 201


@pytest.mark.parametrize("method,path,body", [
    ("post", "/api/catalog/products/", {"sku": "X", "name": "Y"}),
    ("post", "/api/purchasing/stock-ins/", {}),
    ("post", "/api/purchasing/suppliers/", {"name": "S"}),
    ("post", "/api/inventory/movements/adjust/", {}),
    ("get", "/api/inventory/movements/", None),
    ("get", "/api/reports/sales-summary/", None),
    ("get", "/api/auth/users/", None),
])
def test_cashier_is_forbidden_from_admin_endpoints(cashier_api, method, path, body):
    call = getattr(cashier_api, method)
    resp = call(path, body, format="json") if body is not None else call(path)
    assert resp.status_code == 403, f"{method} {path} -> {resp.status_code}"


def test_admin_can_reach_admin_endpoints(admin_api):
    assert admin_api.get("/api/inventory/movements/").status_code == 200
    assert admin_api.get("/api/reports/sales-summary/").status_code == 200
    assert admin_api.get("/api/auth/users/").status_code == 200
    assert admin_api.post(
        "/api/purchasing/suppliers/", {"name": "Acme"}, format="json"
    ).status_code == 201
