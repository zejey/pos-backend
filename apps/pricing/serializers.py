from rest_framework import serializers

from .models import Discount, Promo


class DiscountSerializer(serializers.ModelSerializer):
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = Discount
        fields = [
            "id", "name", "discount_type", "value",
            "is_active", "start_date", "end_date", "is_current",
            "minimum_purchase", "max_discount_cap", "min_items_required", "min_final_total_percent",
        ]

    def get_is_current(self, obj):
        return obj.is_available()

    def validate(self, attrs):
        discount_type = attrs.get("discount_type", getattr(self.instance, "discount_type", None))
        value = attrs.get("value", getattr(self.instance, "value", None))
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        min_items = attrs.get("min_items_required", getattr(self.instance, "min_items_required", None))
        min_purchase = attrs.get("minimum_purchase", getattr(self.instance, "minimum_purchase", None))
        max_cap = attrs.get("max_discount_cap", getattr(self.instance, "max_discount_cap", None))
        min_final = attrs.get("min_final_total_percent", getattr(self.instance, "min_final_total_percent", None))

        if value is not None and value <= 0:
            raise serializers.ValidationError({"value": "Discount value must be greater than zero."})
        if discount_type == Discount.Type.PERCENTAGE and value is not None and value > 100:
            raise serializers.ValidationError({"value": "Percentage discount cannot exceed 100%."})
        if start and end and start > end:
            raise serializers.ValidationError({"end_date": "End date cannot be earlier than start date."})
        if min_items is not None and min_items < 1:
            raise serializers.ValidationError({"min_items_required": "Minimum items must be at least 1."})
        if min_purchase is not None and min_purchase < 0:
            raise serializers.ValidationError({"minimum_purchase": "Minimum purchase cannot be negative."})
        if max_cap is not None and max_cap <= 0:
            raise serializers.ValidationError({"max_discount_cap": "Max discount cap must be greater than zero."})
        if min_final is not None and (min_final < 0 or min_final > 100):
            raise serializers.ValidationError({"min_final_total_percent": "Minimum final total percent must be between 0 and 100."})
        return attrs


class PromoSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = Promo
        fields = [
            "id", "product", "product_name", "promo_price",
            "start_date", "end_date", "is_active", "is_current",
        ]

    def get_is_current(self, obj):
        return obj.is_available()

    def validate(self, attrs):
        promo_price = attrs.get("promo_price", getattr(self.instance, "promo_price", None))
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))

        if promo_price is not None and promo_price <= 0:
            raise serializers.ValidationError({"promo_price": "Promo price must be greater than zero."})
        if start and end and start > end:
            raise serializers.ValidationError({"end_date": "End date cannot be earlier than start date."})
        return attrs
