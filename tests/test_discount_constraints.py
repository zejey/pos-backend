"""Tests for discount business rule constraints."""
from decimal import Decimal

import pytest

from apps.pricing.models import Discount
from apps.sales.models import Sale
from apps.sales.services import current_tax_rate, set_sale_items

pytestmark = pytest.mark.django_db


def test_discount_minimum_purchase_requirement(make_product):
    """Discount only applies if subtotal >= minimum_purchase."""
    # Create discount with minimum purchase of 200
    discount = Discount.objects.create(
        name="Min Purchase Test",
        discount_type=Discount.Type.PERCENTAGE,
        value=Decimal("10.00"),
        minimum_purchase=Decimal("200.00"),
        min_items_required=1,  # Override default to test only this constraint
    )

    # Test 1: Subtotal < minimum_purchase, discount should be 0
    assert discount.compute(Decimal("100.00")) == Decimal("0.00")

    # Test 2: Subtotal >= minimum_purchase, discount applies
    assert discount.compute(Decimal("200.00")) == Decimal("20.00")  # 10% of 200
    assert discount.compute(Decimal("300.00")) == Decimal("30.00")  # 10% of 300


def test_discount_max_discount_cap(make_product):
    """Discount is capped at max_discount_cap even if percentage is higher."""
    # Create a 50% discount but cap it at 50
    discount = Discount.objects.create(
        name="Capped Discount",
        discount_type=Discount.Type.PERCENTAGE,
        value=Decimal("50.00"),
        max_discount_cap=Decimal("50.00"),
        min_items_required=1,  # Override default to test only this constraint
        min_final_total_percent=Decimal("0.00"),  # No margin preservation for this test
    )

    # 50% of 200 = 100, but capped at 50
    assert discount.compute(Decimal("200.00")) == Decimal("50.00")
    # 50% of 100 = 50, capped at 50
    assert discount.compute(Decimal("100.00")) == Decimal("50.00")
    # 50% of 80 = 40, within cap
    assert discount.compute(Decimal("80.00")) == Decimal("40.00")


def test_discount_min_items_required(make_product):
    """Discount only applies if cart has minimum number of items."""
    discount = Discount.objects.create(
        name="Multi-Item Discount",
        discount_type=Discount.Type.FIXED,
        value=Decimal("20.00"),
        min_items_required=2,
    )

    # Single item: no discount
    assert discount.compute(Decimal("100.00"), item_count=1) == Decimal("0.00")

    # 2 items: discount applies
    assert discount.compute(Decimal("100.00"), item_count=2) == Decimal("20.00")

    # 3 items: discount still applies
    assert discount.compute(Decimal("100.00"), item_count=3) == Decimal("20.00")


def test_discount_min_final_total_percent(make_product):
    """Discount never leaves final total below minimum percent of subtotal."""
    # 10% minimum final total = can't discount more than 90%
    discount = Discount.objects.create(
        name="Preserve Margin",
        discount_type=Discount.Type.PERCENTAGE,
        value=Decimal("100.00"),  # Try to discount 100%
        min_final_total_percent=Decimal("10.00"),  # But keep at least 10% of subtotal
        min_items_required=1,  # Override default to test only this constraint
    )

    # Even though discount is 100%, it gets capped to leave 10%
    # Subtotal 100, min final = 10, so max discount = 90
    assert discount.compute(Decimal("100.00")) == Decimal("90.00")

    # Subtotal 200, min final = 20, so max discount = 180
    assert discount.compute(Decimal("200.00")) == Decimal("180.00")


def test_discount_all_constraints_combined(make_product):
    """Multiple constraints apply together."""
    discount = Discount.objects.create(
        name="Complex Discount",
        discount_type=Discount.Type.PERCENTAGE,
        value=Decimal("50.00"),
        minimum_purchase=Decimal("100.00"),
        max_discount_cap=Decimal("40.00"),
        min_items_required=2,
        min_final_total_percent=Decimal("20.00"),
    )

    # Below minimum purchase: no discount
    assert discount.compute(Decimal("50.00"), item_count=2) == Decimal("0.00")

    # Only 1 item: no discount
    assert discount.compute(Decimal("200.00"), item_count=1) == Decimal("0.00")

    # Valid: 200 subtotal, 2 items
    # 50% of 200 = 100
    # Capped at 40 by max_discount_cap
    # Min final total = 40, max discount = 160, so 40 is OK
    assert discount.compute(Decimal("200.00"), item_count=2) == Decimal("40.00")


def test_discount_with_sale_integration(make_product, cashier_api):
    """Test discount constraints work in actual sale flow."""
    product = make_product(qty=Decimal("10"), price=Decimal("100.00"))
    
    # Create a discount that requires 2+ items
    discount = Discount.objects.create(
        name="Multi-Item Only",
        discount_type=Discount.Type.PERCENTAGE,
        value=Decimal("10.00"),
        min_items_required=2,
        is_active=True,
    )

    # Test 1: Sale with 1 item and discount applied
    sale = Sale.objects.create(tax_rate=current_tax_rate(), discount=discount)
    set_sale_items(sale, [{"product": product.pk, "quantity": Decimal("1")}])
    # Discount should NOT apply (only 1 item)
    assert sale.discount_total == Decimal("0.00")
    assert sale.total == Decimal("100.00")

    # Test 2: Sale with 2 items and discount applied
    sale2 = Sale.objects.create(tax_rate=current_tax_rate(), discount=discount)
    set_sale_items(sale2, [
        {"product": product.pk, "quantity": Decimal("1")},
        {"product": product.pk, "quantity": Decimal("1")},
    ])
    # Discount should apply (2 items)
    assert sale2.discount_total == Decimal("20.00")  # 10% of 200
    assert sale2.total == Decimal("180.00")
