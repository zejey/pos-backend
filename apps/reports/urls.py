from django.urls import path

from .views import (
    InventoryStatusReport,
    ProfitEstimateReport,
    SalesSummaryReport,
    StockInHistoryReport,
    TopProductsReport,
)

urlpatterns = [
    path("sales-summary/", SalesSummaryReport.as_view(), name="report-sales-summary"),
    path("top-products/", TopProductsReport.as_view(), name="report-top-products"),
    path("inventory-status/", InventoryStatusReport.as_view(), name="report-inventory-status"),
    path("stock-in-history/", StockInHistoryReport.as_view(), name="report-stock-in-history"),
    path("profit-estimate/", ProfitEstimateReport.as_view(), name="report-profit-estimate"),
]
