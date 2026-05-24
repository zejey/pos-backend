from rest_framework.routers import DefaultRouter

from .views import DiscountViewSet, PromoViewSet

router = DefaultRouter()
router.register("discounts", DiscountViewSet, basename="discount")
router.register("promos", PromoViewSet, basename="promo")

urlpatterns = router.urls
