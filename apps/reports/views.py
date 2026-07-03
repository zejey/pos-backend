"""Reports & Analytics (read-only aggregations). Admin only.

All figures are derived from the same source data the controlled flow records,
so reports are always consistent with the ledger.
"""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP


from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Product
from apps.common.formatting import format_local_date
from apps.common.pagination import DefaultPagination
from apps.common.permissions import IsAdmin
from apps.purchasing.models import StockIn
from apps.sales.models import Sale, SaleItem

ZERO = Decimal("0.00")
TWO_DP = Decimal("0.01")
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
            total_tax=Coalesce(Sum("tax_amount"), ZERO),
        )
        return Response({
            "period": period,
            "start": format_local_date(start),
            "end": format_local_date(end),
            "transactions": agg["transactions"],
            "gross_sales": agg["gross_sales"],
            "total_discount": agg["total_discount"],
            "total_tax": agg["total_tax"],
            "net_of_tax": agg["gross_sales"] - agg["total_tax"],
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
        limit = max(1, min(limit, 100))  # bound the result size

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
        return Response({
            "start": format_local_date(start),
            "end": format_local_date(end),
            "results": list(rows),
        })


class InventoryStatusReport(APIView):
    """Current stock snapshot with valuation and low-stock flags (Reports 1.3)."""

    permission_classes = [IsAdmin]

    def get(self, request):
        qs = (
            Product.objects.filter(is_active=True)
            .select_related("category")
            .annotate(
                value=ExpressionWrapper(
                    F("quantity_on_hand") * F("cost_price"), output_field=MONEY
                ),
            )
            .order_by("quantity_on_hand")
        )
        # Summary totals span the WHOLE catalog (not just the current page).
        totals = qs.aggregate(
            product_count=Count("id"),
            total_stock_value=Coalesce(Sum("value"), ZERO),
            low_stock_count=Count(
                "id", filter=Q(quantity_on_hand__lte=F("reorder_level"))
            ),
        )

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        items = [{
            "id": p.id, "sku": p.sku, "name": p.name,
            "quantity_on_hand": p.quantity_on_hand,
            "reorder_level": p.reorder_level,
            "is_low_stock": p.quantity_on_hand <= p.reorder_level,
            "stock_value": p.value,
        } for p in page]

        response = paginator.get_paginated_response(items)
        response.data["product_count"] = totals["product_count"]
        response.data["low_stock_count"] = totals["low_stock_count"]
        response.data["total_stock_value"] = totals["total_stock_value"]
        return response


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
            .select_related("supplier")
            .prefetch_related("items")
            .order_by("-purchase_date")
        )
        results = [{
            "id": s.id,
            "reference_no": s.reference_no,
            "supplier": s.supplier.name if s.supplier else None,
            "purchase_date": format_local_date(s.purchase_date),
            "total_cost": s.total_cost,
            "item_count": s.items.count(),
        } for s in stock_ins]
        total = sum((r["total_cost"] for r in results), ZERO)
        return Response({
            "start": format_local_date(start),
            "end": format_local_date(end),
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
            "start": format_local_date(start),
            "end": format_local_date(end),
            "revenue": revenue,
            "estimated_cogs": cogs,
            "estimated_profit": (revenue - cogs),
        })


class DashboardReport(APIView):
    """One-call KPI snapshot for the dashboard (FEAT-12).

    Bundles today's sales, low-stock count, and today's top item so the
    frontend dashboard loads with a single request instead of several.
    """

    permission_classes = [IsAdmin]

    def get(self, request):
        today = timezone.localdate()
        todays_sales = Sale.objects.filter(
            status=Sale.Status.COMPLETED, completed_at__date=today
        )
        sales_agg = todays_sales.aggregate(
            transactions=Count("id"),
            gross_sales=Coalesce(Sum("total"), ZERO),
            total_tax=Coalesce(Sum("tax_amount"), ZERO),
        )
        low_stock_count = Product.objects.filter(
            is_active=True, quantity_on_hand__lte=F("reorder_level")
        ).count()
        top = (
            SaleItem.objects.filter(
                sale__status=Sale.Status.COMPLETED, sale__completed_at__date=today
            )
            .values("product", "product__name")
            .annotate(quantity_sold=Coalesce(Sum("quantity"), ZERO))
            .order_by("-quantity_sold")
            .first()
        )
        return Response({
            "date": format_local_date(today),
            "today": {
                "transactions": sales_agg["transactions"],
                "gross_sales": sales_agg["gross_sales"],
                "total_tax": sales_agg["total_tax"],
            },
            "low_stock_count": low_stock_count,
            "top_item": {
                "product": top["product"],
                "name": top["product__name"],
                "quantity_sold": top["quantity_sold"],
            } if top else None,
        })

class InventoryTurnoverReport(APIView):
    """Inventory turnover rate per product for a given date range.
 
    Formula
    -------
    Turnover Rate = COGS (units sold * cost_price) / Average Inventory Value
 
    Average Inventory Value is approximated as:
        (opening_stock_value + closing_stock_value) / 2
 
    where:
      - closing stock value  = quantity_on_hand * cost_price  (right now)
      - opening stock value  = (quantity_on_hand + net_sold_in_period) * cost_price
 
    This is the standard retail approximation. It deliberately uses the
    *current* cost_price for both sides so the ratio is internally consistent
    (same limitation as ProfitEstimateReport — not audited FIFO/WACC).
 
    Query params
    ------------
    start, end : YYYY-MM-DD  — defaults to today
    limit      : int 1-200   — rows to return, sorted by turnover desc
 
    Response fields (per product)
    ------------------------------
    product, sku, name
    units_sold          — total qty sold in the period
    cogs                — units_sold * cost_price
    opening_stock_value — estimated value at period start
    closing_stock_value — value at period end (current)
    avg_inventory_value — (open + close) / 2
    turnover_rate       — cogs / avg_inventory_value  (null if avg == 0)
    days_to_sell        — period_days / turnover_rate  (null if turnover == 0)
    """
 
    permission_classes = [IsAdmin]
 
    def get(self, request):
        start, end = _parse_range(request)
        try:
            limit = max(1, min(int(request.query_params.get("limit", 25)), 200))
        except ValueError:
            limit = 25
 
        period_days = (end - start).days + 1  # inclusive
 
        # --- units sold per product in the period ---
        sold_qs = (
            SaleItem.objects.filter(
                sale__status=Sale.Status.COMPLETED,
                sale__completed_at__date__range=(start, end),
            )
            .values("product_id")
            .annotate(units_sold=Coalesce(Sum("quantity"), ZERO, output_field=DecimalField()))
        )
        sold_map = {row["product_id"]: row["units_sold"] for row in sold_qs}
 
        # --- active products ---
        products = (
            Product.objects.filter(is_active=True)
            .select_related("category")
            .only(
                "id",
                "sku",
                "name",
                "quantity_on_hand",
                "cost_price",
                "category",
            )
        )
 
        rows = []
        for p in products:
            units_sold = sold_map.get(p.id, ZERO)
            cost = p.cost_price or ZERO
 
            closing_val = (p.quantity_on_hand * cost).quantize(TWO_DP)
            opening_qty = p.quantity_on_hand + units_sold   # add back what was sold
            opening_val = (opening_qty * cost).quantize(TWO_DP)
            avg_val = ((opening_val + closing_val) / 2).quantize(TWO_DP)
 
            cogs = (units_sold * cost).quantize(TWO_DP)
 
            if avg_val and avg_val > 0:
                turnover = float((cogs / avg_val).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
                days_to_sell = round(period_days / turnover, 1) if turnover > 0 else None
            else:
                turnover = None
                days_to_sell = None
 
            rows.append({
                "product": p.id,
                "sku": p.sku,
                "name": p.name,
                "units_sold": units_sold,
                "cogs": cogs,
                "opening_stock_value": opening_val,
                "closing_stock_value": closing_val,
                "avg_inventory_value": avg_val,
                "turnover_rate": turnover,
                "days_to_sell": days_to_sell,
            })
 
        # Sort by turnover descending (None last)
        rows.sort(key=lambda r: r["turnover_rate"] if r["turnover_rate"] is not None else -1, reverse=True)
        rows = rows[:limit]
 
        # --- aggregate summary ---
        total_cogs = sum(r["cogs"] for r in rows)
        total_avg_inv = sum(r["avg_inventory_value"] for r in rows)
        overall_turnover = (
            float((total_cogs / total_avg_inv).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
            if total_avg_inv > 0 else None
        )
 
        return Response({
            "start": start,
            "end": end,
            "period_days": period_days,
            "summary": {
                "total_cogs": total_cogs,
                "total_avg_inventory_value": total_avg_inv,
                "overall_turnover_rate": overall_turnover,
            },
            "results": rows,
        })
 
 
# ---------------------------------------------------------------------------
# Reorder Point
# ---------------------------------------------------------------------------
 
class ReorderPointReport(APIView):
    """Suggested reorder points per product based on actual sales velocity.
 
    Formula
    -------
    Reorder Point (ROP) = (Average Daily Demand × Lead Time) + Safety Stock
 
    where:
      Average Daily Demand = total units sold in the lookback window / lookback_days
      Lead Time            = lead_time_days param (default 7)
      Safety Stock         = z_score * std_daily_demand * sqrt(lead_time_days)
                             — simplified here as a multiplier on avg demand:
                             safety_stock = avg_daily_demand * lead_time_days * safety_factor
 
      safety_factor        = safety_factor param (default 0.5, i.e. 50 % buffer)
 
    The suggested ROP is rounded up to the nearest whole unit.
 
    Because this project has no per-product lead-time field yet, lead_time_days
    is a single query-level input. You can add a `lead_time_days` field to
    Product later and swap the formula to use it per row.
 
    Query params
    ------------
    days          : int  — lookback window for demand calculation (default 30)
    lead_time_days: int  — supplier lead time in days (default 7)
    safety_factor : float — safety stock multiplier on avg_daily_demand * lead_time (default 0.5)
    low_stock_only: bool  — if "true", return only products at or below current reorder_level
 
    Response fields (per product)
    ------------------------------
    product, sku, name, category
    quantity_on_hand
    current_reorder_level       — the value already stored on the product
    avg_daily_demand            — units/day over the lookback window
    lead_time_days              — input param echoed back
    safety_stock                — calculated buffer quantity
    suggested_reorder_point     — ROP = (avg_daily_demand * lead_time_days) + safety_stock
    suggested_reorder_qty       — how much to order (Economic Order Qty not modelled; returns
                                   30-day demand as a sensible default)
    needs_reorder               — True if quantity_on_hand <= suggested_reorder_point
    delta_from_current          — suggested_reorder_point - current_reorder_level
    """
 
    permission_classes = [IsAdmin]
 
    def get(self, request):
        # --- inputs ---
        try:
            lookback_days = max(1, int(request.query_params.get("days", 30)))
        except ValueError:
            lookback_days = 30
 
        try:
            lead_time_days = max(1, int(request.query_params.get("lead_time_days", 7)))
        except ValueError:
            lead_time_days = 7
 
        try:
            safety_factor = max(0.0, float(request.query_params.get("safety_factor", 0.5)))
        except ValueError:
            safety_factor = 0.5
 
        low_stock_only = request.query_params.get("low_stock_only", "").lower() == "true"
 
        end = timezone.localdate()
        start = end - timedelta(days=lookback_days - 1)
 
        # --- sales velocity per product over the lookback window ---
        sold_qs = (
            SaleItem.objects.filter(
                sale__status=Sale.Status.COMPLETED,
                sale__completed_at__date__range=(start, end),
            )
            .values("product_id")
            .annotate(
                total_sold=Coalesce(Sum("quantity"), ZERO, output_field=DecimalField()),
            )
        )
        sold_map = {row["product_id"]: row["total_sold"] for row in sold_qs}
 
        products = (
            Product.objects.filter(is_active=True)
            .select_related("category")
        )
 
        rows = []
        for p in products:
            total_sold = sold_map.get(p.id, ZERO)
            avg_daily = (total_sold / lookback_days).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
 
            safety_stock = (avg_daily * lead_time_days * Decimal(str(safety_factor))).quantize(TWO_DP, rounding=ROUND_HALF_UP)
            rop_raw = (avg_daily * lead_time_days) + safety_stock
            suggested_rop = rop_raw.quantize(TWO_DP, rounding=ROUND_HALF_UP)
 
            # Suggested order qty = 30-day projected demand (simple)
            suggested_order_qty = (avg_daily * 30).quantize(TWO_DP, rounding=ROUND_HALF_UP)
 
            needs_reorder = p.quantity_on_hand <= suggested_rop
            delta = (suggested_rop - p.reorder_level).quantize(TWO_DP)
 
            rows.append({
                "product": p.id,
                "sku": p.sku,
                "name": p.name,
                "category": p.category.name if p.category else None,
                "quantity_on_hand": p.quantity_on_hand,
                "current_reorder_level": p.reorder_level,
                "avg_daily_demand": avg_daily,
                "lead_time_days": lead_time_days,
                "safety_stock": safety_stock,
                "suggested_reorder_point": suggested_rop,
                "suggested_reorder_qty": suggested_order_qty,
                "needs_reorder": needs_reorder,
                "delta_from_current": delta,
            })
 
        if low_stock_only:
            rows = [r for r in rows if r["needs_reorder"]]
 
        # Sort: needs_reorder first, then by delta desc (biggest gap first)
        rows.sort(key=lambda r: (not r["needs_reorder"], -float(r["delta_from_current"])))
 
        reorder_count = sum(1 for r in rows if r["needs_reorder"])
 
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        response = paginator.get_paginated_response(page)
        response.data["lookback_days"] = lookback_days
        response.data["lead_time_days"] = lead_time_days
        response.data["safety_factor"] = safety_factor
        response.data["needs_reorder_count"] = reorder_count
        return response