from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name", "sku", "category", "selling_price",
        "quantity_on_hand", "reorder_level", "is_active",
    )
    list_filter = ("is_active", "category")
    search_fields = ("name", "sku", "barcode")
    readonly_fields = ("quantity_on_hand",)
