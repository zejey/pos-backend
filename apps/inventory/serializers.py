from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import Product

from .models import StockMovement


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    user = serializers.CharField(source="user.username", default=None, read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            "id", "product", "product_sku", "product_name",
            "movement_type", "quantity", "balance_after",
            "reference", "reason", "source_type", "source_id",
            "user", "created_at",
        ]
        read_only_fields = fields


class ManualAdjustmentSerializer(serializers.Serializer):
    """Input for a manual adjustment. Reason is mandatory."""

    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    new_quantity = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
        min_value=Decimal("0.00"),
    )
    delta = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    reason = serializers.CharField(max_length=255)

    def validate(self, attrs):
        if (attrs.get("new_quantity") is None) == (attrs.get("delta") is None):
            raise serializers.ValidationError(
                "Provide exactly one of 'new_quantity' or 'delta'."
            )
        if attrs.get("delta") is not None and attrs["delta"] == 0:
            raise serializers.ValidationError("'delta' must be non-zero.")
        return attrs
