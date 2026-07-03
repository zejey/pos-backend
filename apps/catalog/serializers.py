from decimal import Decimal

from rest_framework import serializers

from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(source="products.count", read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "description", "is_active", "product_count"]


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", default=None, read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    stock_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    reorder_level = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        default=Decimal("5.00"),
        min_value=Decimal("0.00"),
    )

    class Meta:
        model = Product
        fields = [
            "id", "sku", "barcode", "name", "category", "category_name",
            "unit", "cost_price", "selling_price",
            "quantity_on_hand", "reorder_level", "is_low_stock", "stock_value",
            "is_active", "created_at", "updated_at",
        ]
        # quantity_on_hand is controlled by the inventory ledger, never set here.
        read_only_fields = ["quantity_on_hand", "created_at", "updated_at"]


class ProductBatchSerializer(serializers.Serializer):
    """Bulk product entry (Inventory Management 1.6).

    Creates many product definitions in one request. Opening stock is added
    afterwards via stock-in, keeping the controlled flow intact.
    """

    products = ProductSerializer(many=True)

    def create(self, validated_data):
        rows = validated_data["products"]
        objs = [Product(**row) for row in rows]
        return Product.objects.bulk_create(objs)
