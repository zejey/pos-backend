from django.contrib import admin

from .models import StockIn, StockInItem, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_person", "contact_no", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "contact_person", "contact_no")


class StockInItemInline(admin.TabularInline):
    model = StockInItem
    extra = 0


@admin.register(StockIn)
class StockInAdmin(admin.ModelAdmin):
    list_display = ("reference_no", "supplier", "purchase_date", "status", "posted_at")
    list_filter = ("status",)
    search_fields = ("reference_no", "supplier__name")
    autocomplete_fields = ("supplier",)
    inlines = [StockInItemInline]
