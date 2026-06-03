from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.services import log_activity
from apps.common.mixins import ActivityLogMixin
from apps.common.permissions import IsAdminOrReadOnly

from .models import Category, Product
from .serializers import (
    CategorySerializer,
    ProductBatchSerializer,
    ProductSerializer,
)


class CategoryViewSet(ActivityLogMixin, viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["is_active"]
    search_fields = ["name"]


class ProductViewSet(ActivityLogMixin, viewsets.ModelViewSet):
    """Product master data. Cashiers read; Admins manage."""

    queryset = Product.objects.select_related("category").all()
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["category", "is_active"]
    search_fields = ["name", "sku", "barcode"]
    ordering_fields = ["name", "selling_price", "quantity_on_hand"]

    def perform_create(self, serializer):
        product = serializer.save()
        log_activity(self.request.user, "PRODUCT_CREATE", entity="Product",
                     entity_id=product.pk, detail={"sku": product.sku},
                     request=self.request)

    @action(detail=False, methods=["post"])
    def batch(self, request):
        """Bulk-create product definitions."""
        serializer = ProductBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = serializer.save()
        log_activity(request.user, "PRODUCT_BATCH_CREATE", entity="Product",
                     detail={"count": len(created)}, request=request)
        return Response(
            {"created": len(created),
             "products": ProductSerializer(created, many=True).data}
        )
