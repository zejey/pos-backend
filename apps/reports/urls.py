from django.urls import path

from .views import (
    DashboardReport,
    InventoryStatusReport,
    ProfitEstimateReport,
    SalesSummaryReport,
    StockInHistoryReport,
    TopProductsReport,
    InventoryTurnoverReport,
    ReorderPointReport
)

urlpatterns = [
    path("dashboard/", DashboardReport.as_view(), name="report-dashboard"),
    path("sales-summary/", SalesSummaryReport.as_view(), name="report-sales-summary"),
    path("top-products/", TopProductsReport.as_view(), name="report-top-products"),
    path("inventory-status/", InventoryStatusReport.as_view(), name="report-inventory-status"),
    path("stock-in-history/", StockInHistoryReport.as_view(), name="report-stock-in-history"),
    path("profit-estimate/", ProfitEstimateReport.as_view(), name="report-profit-estimate"),
    path("inventory-turnover/", InventoryTurnoverReport.as_view(), name="report-inventory-turnover"),
    path("reorder-point/", ReorderPointReport.as_view(), name="report-reorder-point"),
]
