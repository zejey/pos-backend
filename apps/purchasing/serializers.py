from rest_framework import serializers

from .models import StockIn, StockInItem


class StockInItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    discrepancy_qty = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    line_cost = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )

    class Meta:
        model = StockInItem
        fields = [
            "id", "product", "product_name", "quantity_ordered",
            "quantity_received", "unit_cost", "discrepancy_reason",
            "discrepancy_qty", "line_cost",
        ]

    def validate(self, attrs):
        ordered = attrs.get("quantity_ordered")
        received = attrs.get("quantity_received")
        reason = attrs.get("discrepancy_reason", "")
        if ordered is not None and received is not None:
            if received != ordered and not reason:
                raise serializers.ValidationError(
                    "A discrepancy_reason is required when received quantity "
                    "differs from ordered quantity."
                )
        return attrs


class StockInSerializer(serializers.ModelSerializer):
    items = StockInItemSerializer(many=True)
    total_cost = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True
    )
    created_by = serializers.CharField(
        source="created_by.username", default=None, read_only=True
    )

    class Meta:
        model = StockIn
        fields = [
            "id", "reference_no", "supplier", "purchase_date", "note",
            "status", "created_by", "posted_at", "total_cost", "items",
            "created_at",
        ]
        read_only_fields = ["status", "posted_at", "created_by"]

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        stock_in = StockIn.objects.create(**validated_data)
        StockInItem.objects.bulk_create(
            [StockInItem(stock_in=stock_in, **row) for row in items_data]
        )
        return stock_in

    def update(self, instance, validated_data):
        if instance.status == StockIn.Status.POSTED:
            raise serializers.ValidationError("A posted stock-in cannot be edited.")
        items_data = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            StockInItem.objects.bulk_create(
                [StockInItem(stock_in=instance, **row) for row in items_data]
            )
        return instance
