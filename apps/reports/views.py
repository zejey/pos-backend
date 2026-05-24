"""Reports & Analytics (read-only aggregations). Admin only.

All figures are derived from the same source data the controlled flow records,
so reports are always consistent with the ledger.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Sum,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Product
from apps.common.permissions import IsAdmin
from apps.purchasing.models import StockIn
from apps.sales.models import Sale, SaleItem

ZERO = Decimal("0.00")
MONEY = DecimalField(max_digits=16, decimal_places=2)


def _parse_range(request):
    """Return (start_date, end_date) from ?start=&end=, defaulting to today."""
    today = timezone.localdate()
    start = parse_date(request.query_params.get("start", "")) or today
    end = parse_date(request.query_params.get("end", "")) or today
    return start, end


class SalesSummaryReport(APIView):
    """?period=daily|weekly|monthly&date=YYYY-MM-DD (Reports 1.1)."""

    permission_classes = [IsAdmin]

    def get(self, request):
        period = request.query_params.get("period", "daily")
        ref = parse_date(request.query_params.get("date", "")) or timezone.localdate()

        if period == "weekly":
            start = ref - timedelta(days=ref.weekday())
            end = start + timedelta(days=6)
        elif period == "monthly":
            start = ref.replace(day=1)
            next_month = (start + timedelta(days=32)).replace(day=1)
            end = next_month - timedelta(days=1)
        else:
            period, start, end = "daily", ref, ref

        sales = Sale.objects.filter(
            status=Sale.Status.COMPLETED,
            completed_at__date__range=(start, end),
        )
        agg = sales.aggregate(
            transactions=Count("id"),
            gross_sales=Coalesce(Sum("total"), ZERO),
            total_discount=Coalesce(Sum("discount_total"), ZERO),
        )
        return Response({
            "period": period,
            "start": start,
            "end": end,
            "transactions": agg["transactions"],
            "gross_sales": agg["gross_sales"],
            "total_discount": agg["total_discount"],
        })


class TopProductsReport(APIView):
    """?start=&end=&limit=  Best sellers by quantity and revenue (Reports 1.2)."""

    permission_classes = [IsAdmin]

    def get(self, request):
        start, end = _parse_range(request)
        try:
            limit = int(request.query_params.get("limit", 10))
        except ValueError:
            limit = 10

        rows = (
            SaleItem.objects.filter(
                sale__status=Sale.Status.COMPLETED,
                sale__completed_at__date__range=(start, end),
            )
            .values("product", "product__sku", "product__name")
            .annotate(
                quantity_sold=Coalesce(Sum("quantity"), ZERO),
                revenue=Coalesce(Sum("line_total"), ZERO),
            )
            .order_by("-quantity_sold")[:limit]
        )
        return Response({"start": start, "end": end, "results": list(rows)})


class InventoryStatusReport(APIView):
    """Current stock snapshot with valuation and low-stock flags (Reports 1.3)."""

    permission_classes = [IsAdmin]

    def get(self, request):
        products = Product.objects.filter(is_active=True).select_related("category")
        items, total_value, low_count = [], ZERO, 0
        for p in products:
            value = p.stock_value
            total_value += value
            low = p.is_low_stock
            low_count += 1 if low else 0
            items.append({
                "id": p.id, "sku": p.sku, "name": p.name,
                "quantity_on_hand": p.quantity_on_hand,
                "reorder_level": p.reorder_level,
                "is_low_stock": low,
                "stock_value": value,
            })
        return Response({
            "product_count": len(items),
            "low_stock_count": low_count,
            "total_stock_value": total_value,
            "results": items,
        })


class StockInHistoryReport(APIView):
    """?start=&end=  Posted purchase history (Reports 1.4)."""

    permission_classes = [IsAdmin]

    def get(self, request):
        start, end = _parse_range(request)
        stock_ins = (
            StockIn.objects.filter(
                status=StockIn.Status.POSTED,
                purchase_date__range=(start, end),
            )
            .prefetch_related("items")
            .order_by("-purchase_date")
        )
        results = [{
            "id": s.id,
            "reference_no": s.reference_no,
            "supplier": s.supplier,
            "purchase_date": s.purchase_date,
            "total_cost": s.total_cost,
            "item_count": s.items.count(),
        } for s in stock_ins]
        total = sum((r["total_cost"] for r in results), ZERO)
        return Response({
            "start": start, "end": end,
            "purchase_count": len(results),
            "total_purchase_cost": total,
            "results": results,
        })


class ProfitEstimateReport(APIView):
    """?start=&end=  Basic profit estimation: revenue - estimated COGS (Reports 1.5).

    COGS uses each product's current cost price, so this is an estimate, not
    audited margin accounting.
    """

    permission_classes = [IsAdmin]

    def get(self, request):
        start, end = _parse_range(request)
        items = SaleItem.objects.filter(
            sale__status=Sale.Status.COMPLETED,
            sale__completed_at__date__range=(start, end),
        )
        cogs_expr = ExpressionWrapper(
            F("quantity") * F("product__cost_price"), output_field=MONEY
        )
        agg = items.aggregate(
            revenue=Coalesce(Sum("line_total"), ZERO),
            cogs=Coalesce(Sum(cogs_expr), ZERO),
        )
        revenue, cogs = agg["revenue"], agg["cogs"]
        return Response({
            "start": start, "end": end,
            "revenue": revenue,
            "estimated_cogs": cogs,
            "estimated_profit": (revenue - cogs),
        })
