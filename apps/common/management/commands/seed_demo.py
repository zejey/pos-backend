"""Seed demo data so the team can run/demonstrate the system immediately.

Usage:  python manage.py seed_demo
Creates an admin + cashier, a few categories/products, and one posted
stock-in so products start with stock (following the controlled flow).
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.catalog.models import Category, Product
from apps.purchasing.models import StockIn, StockInItem, Supplier
from apps.purchasing.services import post_stock_in


class Command(BaseCommand):
    help = "Seed demo users, products, and an initial stock-in."

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
