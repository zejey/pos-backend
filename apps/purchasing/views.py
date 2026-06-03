from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.services import log_activity
from apps.common.permissions import IsAdmin

from .models import StockIn, Supplier
from .serializers import StockInSerializer, SupplierSerializer
from .services import post_stock_in


class SupplierViewSet(viewsets.ModelViewSet):
    """Suppliers / vendors. Admin only."""

    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAdmin]
    filterset_fields = ["is_active"]
    search_fields = ["name", "contact_person", "contact_no"]
    ordering_fields = ["name", "created_at"]


class StockInViewSet(viewsets.ModelViewSet):
    """Stock-in / purchase documents. Admin only."""

    queryset = (
        StockIn.objects.select_related("supplier")
        .prefetch_related("items__product")
        .all()
    )
    serializer_class = StockInSerializer
    permission_classes = [IsAdmin]
    filterset_fields = ["status", "supplier"]
    search_fields = ["reference_no", "supplier__name"]
    ordering_fields = ["purchase_date", "created_at"]

    def perform_create(self, serializer):
        stock_in = serializer.save(created_by=self.request.user)
        log_activity(self.request.user, "STOCKIN_CREATE", entity="StockIn",
                     entity_id=stock_in.pk, detail={"reference_no": stock_in.reference_no},
                     request=self.request)

    @action(detail=True, methods=["post"])
    def post_document(self, request, pk=None):
        """Post the stock-in: received quantities flow into inventory."""
        stock_in = self.get_object()
        post_stock_in(stock_in, user=request.user)
        log_activity(request.user, "STOCKIN_POST", entity="StockIn",
                     entity_id=stock_in.pk, detail={"reference_no": stock_in.reference_no},
                     request=request)
        return Response(self.get_serializer(stock_in).data)
