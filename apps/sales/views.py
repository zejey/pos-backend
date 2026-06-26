from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.services import log_activity
from apps.common.permissions import IsAdmin

from .models import Sale, SaleItem, SaleItemVoidRequest
from .serializers import (
    CartItemInputSerializer,
    CompleteSaleSerializer,
    SaleItemVoidRequestApproveSerializer,
    SaleItemVoidRequestCreateSerializer,
    SaleItemVoidRequestReviewSerializer,
    SaleItemVoidRequestSerializer,
    ReceiptSerializer,
    SaleSerializer,
    VoidSaleSerializer,
)
from .services import (
    approve_item_void_request,
    complete_sale,
    deny_item_void_request,
    set_sale_items,
    void_sale,
)


class SaleViewSet(viewsets.ModelViewSet):
    """Point of Sale transactions. Cashiers and admins can sell."""

    queryset = Sale.objects.prefetch_related("items__product", "payments").all()
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "cashier"]
    search_fields = ["receipt_no"]
    ordering_fields = ["created_at", "completed_at", "total"]

    def perform_create(self, serializer):
        sale = serializer.save()
        log_activity(self.request.user, "SALE_DRAFT_CREATE", entity="Sale",
                     entity_id=sale.pk, request=self.request)

    @action(detail=True, methods=["post"])
    def set_items(self, request, pk=None):
        """Replace the cart's items (add/remove from cart, POS 1.2)."""
        sale = self.get_object()
        serializer = CartItemInputSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        set_sale_items(sale, serializer.validated_data)
        return Response(self.get_serializer(sale).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Take payment, deduct stock, issue receipt (POS 1.3-1.5)."""
        sale = self.get_object()
        serializer = CompleteSaleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = complete_sale(sale, serializer.validated_data["payments"], user=request.user)
        log_activity(request.user, "SALE_COMPLETE", entity="Sale",
                     entity_id=sale.pk,
                     detail={"receipt_no": sale.receipt_no, "total": str(sale.total)},
                     request=request)
        return Response(self.get_serializer(sale).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    def void(self, request, pk=None):
        """Void a completed sale and return items to stock (admin only)."""
        sale = self.get_object()
        serializer = VoidSaleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = void_sale(sale, serializer.validated_data["reason"], user=request.user)
        log_activity(request.user, "SALE_VOID", entity="Sale",
                     entity_id=sale.pk,
                     detail={"receipt_no": sale.receipt_no}, request=request)
        return Response(self.get_serializer(sale).data)

    @action(detail=True, methods=["get"])
    def receipt(self, request, pk=None):
        """Receipt payload for printing (POS 1.5)."""
        return Response(ReceiptSerializer(self.get_object()).data)

    @action(detail=False, methods=["get"])
    def daily_summary(self, request):
        """Today's sales totals (POS 1.6 daily sales tracking)."""
        today = timezone.localdate()
        qs = Sale.objects.filter(
            status=Sale.Status.COMPLETED, completed_at__date=today
        )
        agg = qs.aggregate(
            count=Count("id"), total=Sum("total"), tax=Sum("tax_amount")
        )
        return Response({
            "date": today,
            "transactions": agg["count"] or 0,
            "gross_sales": agg["total"] or Decimal("0.00"),
            "total_tax": agg["tax"] or Decimal("0.00"),
        })


class SaleItemVoidRequestViewSet(viewsets.ModelViewSet):
    queryset = SaleItemVoidRequest.objects.all()
    serializer_class = SaleItemVoidRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = SaleItemVoidRequest.objects.select_related(
            "sale", "requested_by", "reviewed_by"
        )
        if getattr(self.request.user, "is_admin", False):
            return qs
        return qs.filter(requested_by=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return SaleItemVoidRequestCreateSerializer
        if self.action == "approve":
            return SaleItemVoidRequestApproveSerializer
        if self.action == "deny":
            return SaleItemVoidRequestReviewSerializer
        return SaleItemVoidRequestSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_obj = serializer.save()
        log_activity(self.request.user, "SALE_ITEM_VOID_REQUEST", entity="SaleItemVoidRequest",
                     entity_id=request_obj.pk, detail={"sale_id": request_obj.sale_id},
                     request=self.request)
        output = SaleItemVoidRequestSerializer(request_obj, context=self.get_serializer_context())
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=201, headers=headers)

    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    def approve(self, request, pk=None):
        request_obj = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_obj = approve_item_void_request(
            request_obj,
            request.user,
            review_note=serializer.validated_data.get("review_note", ""),
        )
        log_activity(request.user, "SALE_ITEM_VOID_APPROVE", entity="SaleItemVoidRequest",
                     entity_id=request_obj.pk, detail={"sale_id": request_obj.sale_id},
                     request=request)
        return Response(SaleItemVoidRequestSerializer(request_obj).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    def deny(self, request, pk=None):
        request_obj = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_obj = deny_item_void_request(
            request_obj,
            request.user,
            review_note=serializer.validated_data.get("review_note", ""),
        )
        log_activity(request.user, "SALE_ITEM_VOID_DENY", entity="SaleItemVoidRequest",
                     entity_id=request_obj.pk, detail={"sale_id": request_obj.sale_id},
                     request=request)
        return Response(SaleItemVoidRequestSerializer(request_obj).data)
