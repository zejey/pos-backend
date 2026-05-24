from django.contrib import admin

from .models import StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "created_at", "product", "movement_type",
        "quantity", "balance_after", "reference", "user",
    )
    list_filter = ("movement_type",)
    search_fields = ("product__sku", "product__name", "reference", "reason")
    readonly_fields = [f.name for f in StockMovement._meta.fields]

    def has_add_permission(self, request):
        # Ledger is append-only via the service layer, never by hand.
        return False

    def has_change_permission(self, request, obj=None):
        return False
