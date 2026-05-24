from django.contrib import admin

from .models import Discount, Promo


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ("name", "discount_type", "value", "is_active", "start_date", "end_date")
    list_filter = ("discount_type", "is_active")


@admin.register(Promo)
class PromoAdmin(admin.ModelAdmin):
    list_display = ("product", "promo_price", "is_active", "start_date", "end_date")
    list_filter = ("is_active",)
    search_fields = ("product__sku", "product__name")
