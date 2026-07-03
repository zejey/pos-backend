import csv

from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.services import log_activity
from apps.catalog.models import Product
from apps.catalog.serializers import ProductSerializer
from apps.common.formatting import format_local_datetime
from apps.common.permissions import IsAdmin

from .models import StockMovement
from .serializers import ManualAdjustmentSerializer, StockMovementSerializer
from .services import manual_adjustment


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only inventory audit trail (every stock change ever made)."""

    queryset = StockMovement.objects.select_related("product", "user").all()
    serializer_class = StockMovementSerializer
    permission_classes = [IsAdmin]
    filterset_fields = ["product", "movement_type", "source_type"]
    search_fields = ["product__sku", "product__name", "reference", "reason"]
    ordering_fields = ["created_at"]

    @action(detail=False, methods=["post"])
    def adjust(self, request):
        """Manual stock adjustment with reason logging (Inventory 1.5)."""
        serializer = ManualAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        movement = manual_adjustment(
            product=data["product"],
            new_quantity=data.get("new_quantity"),
            delta=data.get("delta"),
            reason=data["reason"],
            user=request.user,
        )
        log_activity(
            request.user, "STOCK_ADJUSTMENT", entity="Product",
            entity_id=data["product"].pk,
            detail={"quantity": str(movement.quantity), "reason": data["reason"]},
            request=request,
        )
        return Response(StockMovementSerializer(movement).data)

    @action(detail=False, methods=["get"])
    def low_stock(self, request):
        """Products at or below their reorder level (Inventory 1.4)."""
        from django.db.models import F

        products = (
            Product.objects.filter(is_active=True, quantity_on_hand__lte=F("reorder_level"))
            .select_related("category")
            .order_by("quantity_on_hand")
        )
        return Response(ProductSerializer(products, many=True).data)

    @action(detail=False, methods=["get"])
    def export(self, request):
        """Export the filtered inventory audit trail as CSV."""
        movements = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="inventory-movements.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "created_at", "product_sku", "product_name", "movement_type",
            "quantity", "balance_after", "reference", "reason",
            "source_type", "source_id", "user",
        ])
        for movement in movements:
            writer.writerow([
                format_local_datetime(movement.created_at),
                movement.product.sku,
                movement.product.name,
                movement.movement_type,
                movement.quantity,
                movement.balance_after,
                movement.reference,
                movement.reason,
                movement.source_type,
                movement.source_id,
                movement.user.username if movement.user else "",
            ])
        return response
