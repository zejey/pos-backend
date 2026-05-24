from rest_framework import viewsets

from apps.common.permissions import IsAdminOrReadOnly

from .models import Discount, Promo
from .serializers import DiscountSerializer, PromoSerializer


class DiscountViewSet(viewsets.ModelViewSet):
    queryset = Discount.objects.all()
    serializer_class = DiscountSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["discount_type", "is_active"]
    search_fields = ["name"]


class PromoViewSet(viewsets.ModelViewSet):
    queryset = Promo.objects.select_related("product").all()
    serializer_class = PromoSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["product", "is_active"]
