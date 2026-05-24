from rest_framework.routers import DefaultRouter

from .views import StockInViewSet

router = DefaultRouter()
router.register("stock-ins", StockInViewSet, basename="stockin")

urlpatterns = router.urls
