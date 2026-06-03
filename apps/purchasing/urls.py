from rest_framework.routers import DefaultRouter

from .views import StockInViewSet, SupplierViewSet

router = DefaultRouter()
router.register("suppliers", SupplierViewSet, basename="supplier")
router.register("stock-ins", StockInViewSet, basename="stockin")

urlpatterns = router.urls
