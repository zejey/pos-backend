"""Seed demo data so the team can run/demonstrate the system immediately.

Usage:  python manage.py seed_demo
Creates an admin + cashier, a few categories/products, one posted stock-in so
products start with stock, and a handful of completed sales so the reports /
analytics endpoints return meaningful data right away. Everything follows the
controlled flow (stock-in -> inventory -> POS sale).
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.catalog.models import Category, Product
from apps.pricing.models import Discount
from apps.purchasing.models import StockIn, StockInItem, Supplier
from apps.purchasing.services import post_stock_in
from apps.sales.models import Payment, Sale
from apps.sales.services import complete_sale, current_tax_rate, set_sale_items


class Command(BaseCommand):
    help = "Seed demo users, products, an initial stock-in, and sample sales."

    def handle(self, *args, **options):
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={"role": User.Role.ADMIN, "is_staff": True, "is_superuser": True},
        )
        if created:
            admin.set_password("admin123")
            admin.save()
            self.stdout.write("Created admin / admin123")

        cashier, created = User.objects.get_or_create(
            username="cashier", defaults={"role": User.Role.CASHIER}
        )
        if created:
            cashier.set_password("cashier123")
            cashier.save()
            self.stdout.write("Created cashier / cashier123")

        if Product.objects.exists():
            self.stdout.write(self.style.WARNING("Products already exist; skipping catalog seed."))
            return

        drinks = Category.objects.create(name="Drinks")
        snacks = Category.objects.create(name="Snacks")
        catalog = [
            ("BEV-001", "Bottled Water 500ml", drinks, "15.00", "10.00", 24),
            ("BEV-002", "Soft Drink Can", drinks, "30.00", "22.00", 24),
            ("BEV-003", "3-in-1 Coffee Sachet", drinks, "12.00", "8.00", 50),
            ("SNK-001", "Potato Chips", snacks, "25.00", "18.00", 30),
            ("SNK-002", "Biscuits", snacks, "10.00", "6.50", 40),
            ("SNK-003", "Instant Noodles", snacks, "13.00", "9.00", 60),
        ]
        products = []
        for sku, name, cat, sell, cost, reorder in catalog:
            products.append(Product.objects.create(
                sku=sku, name=name, category=cat,
                selling_price=Decimal(sell), cost_price=Decimal(cost),
                reorder_level=Decimal(reorder),
            ))

        supplier = Supplier.objects.create(
            name="Demo Supplier", contact_person="Juan dela Cruz",
            contact_no="0917-000-0000",
        )
        si = StockIn.objects.create(
            reference_no="SEED-INV-001", supplier=supplier,
            purchase_date=date.today(), created_by=admin,
        )
        for prod in products:
            StockInItem.objects.create(
                stock_in=si, product=prod,
                quantity_ordered=Decimal("100"), quantity_received=Decimal("100"),
                unit_cost=prod.cost_price,
            )
        post_stock_in(si, user=admin)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(products)} products with 100 units each via stock-in {si.reference_no}."
        ))

        # A standing order-level discount, applied to one sample sale below so
        # the sales-summary "total_discount" figure is non-zero in demos.
        discount = Discount.objects.create(
            name="Suki 10% Off", discount_type=Discount.Type.PERCENTAGE,
            value=Decimal("10"), is_active=True,
        )

        # Sample sales through the real POS flow so reports/analytics have data.
        # (product index: 0 water, 1 soft drink, 2 coffee, 3 chips, 4 biscuits,
        # 5 noodles.) The product mix is varied so top-products ranks sensibly.
        sample_sales = [
            (cashier, None, [(0, "10"), (2, "5")]),
            (cashier, discount, [(1, "6"), (3, "4")]),
            (admin, None, [(5, "8"), (4, "12")]),
        ]
        tax_rate = current_tax_rate()
        for seller, disc, lines in sample_sales:
            sale = Sale.objects.create(
                cashier=seller, discount=disc, tax_rate=tax_rate,
            )
            set_sale_items(sale, [
                {"product": products[idx], "quantity": Decimal(qty)}
                for idx, qty in lines
            ])
            sale.refresh_from_db()
            complete_sale(
                sale,
                [{"method": Payment.Method.CASH,
                  "amount": sale.total, "tendered": sale.total}],
                user=seller,
            )

        self.stdout.write(self.style.SUCCESS(
            f"Recorded {len(sample_sales)} completed sales so reports/analytics "
            "show data immediately."
        ))
