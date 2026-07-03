from rest_framework import serializers

from .models import Discount, Promo


class DiscountSerializer(serializers.ModelSerializer):
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = Discount
        fields = [
            "id", "name", "discount_type", "value",
            "is_active", "start_date", "end_date", "is_current",
        ]

    def get_is_current(self, obj):
        return obj.is_available()

    def validate(self, attrs):
        discount_type = attrs.get("discount_type", getattr(self.instance, "discount_type", None))
        value = attrs.get("value", getattr(self.instance, "value", None))
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))

        if value is not None and value <= 0:
            raise serializers.ValidationError({"value": "Discount value must be greater than zero."})
        if discount_type == Discount.Type.PERCENTAGE and value is not None and value > 100:
            raise serializers.ValidationError({"value": "Percentage discount cannot exceed 100%."})
        if start and end and start > end:
            raise serializers.ValidationError({"end_date": "End date cannot be earlier than start date."})
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
