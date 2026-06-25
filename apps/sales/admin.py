from django.contrib import admin

from .models import Payment, Sale, SaleItem, SaleItemVoidRequest


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ("product", "quantity", "unit_price", "line_total")


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("receipt_no", "status", "cashier", "total", "completed_at")
    list_filter = ("status",)
    search_fields = ("receipt_no",)
    inlines = [SaleItemInline, PaymentInline]


@admin.register(SaleItemVoidRequest)
class SaleItemVoidRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id", "sale", "product_sku", "quantity", "status", "requested_by", "reviewed_by", "created_at"
    )
    list_filter = ("status",)
    search_fields = ("product_sku", "product_name", "sale__receipt_no")
