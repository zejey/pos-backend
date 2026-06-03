"""Pytest bootstrap + shared fixtures.

Forces the fast sqlite engine for tests (TEST-00) BEFORE Django settings are
imported, so the suite needs no Postgres. Concurrency tests that rely on
SELECT FOR UPDATE are skipped on sqlite (see tests/test_edge_cases.py).
"""
import os

os.environ.setdefault("POS_DB_ENGINE", "sqlite")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-long-enough-for-hmac-sha256-aaaa")
os.environ.setdefault("POS_TAX_RATE", "12")

from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402
from model_bakery import baker  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin_user(db):
    from apps.accounts.models import User
    return User.objects.create_user(
        username="admin", password="pass12345", role="ADMIN", is_staff=True
    )


@pytest.fixture
def cashier_user(db):
    from apps.accounts.models import User
    return User.objects.create_user(
        username="cashier", password="pass12345", role="CASHIER"
    )


@pytest.fixture
def admin_api(api, admin_user):
    api.force_authenticate(user=admin_user)
    return api


@pytest.fixture
def cashier_api(api, cashier_user):
    api.force_authenticate(user=cashier_user)
    return api


@pytest.fixture
def make_product(db):
    """Create an active, priced product and stock it via the controlled gateway."""
    def _make(qty=Decimal("100"), price=Decimal("100.00"),
              cost=Decimal("60.00"), active=True, **kwargs):
        from apps.catalog.models import Product
        from apps.inventory.models import StockMovement
        from apps.inventory.services import apply_movement

        product = baker.make(
            Product, selling_price=price, cost_price=cost,
            is_active=active, reorder_level=Decimal("5.00"), **kwargs,
        )
        if qty:
            apply_movement(
                product=product, quantity=Decimal(qty),
                movement_type=StockMovement.Type.OPENING,
            )
            product.refresh_from_db()
        return product
    return _make
