from rest_framework.routers import DefaultRouter

from .views import SaleItemVoidRequestViewSet, SaleViewSet

router = DefaultRouter()
router.register("sales", SaleViewSet, basename="sale")
router.register("item-void-requests", SaleItemVoidRequestViewSet, basename="sale-item-void-request")

urlpatterns = router.urls
