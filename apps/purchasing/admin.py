from django.contrib import admin

from .models import StockIn, StockInItem


class StockInItemInline(admin.TabularInline):
    model = StockInItem
    extra = 0


@admin.register(StockIn)
class StockInAdmin(admin.ModelAdmin):
    list_display = ("reference_no", "supplier", "purchase_date", "status", "posted_at")
    list_filter = ("status",)
    search_fields = ("reference_no", "supplier")
    inlines = [StockInItemInline]
