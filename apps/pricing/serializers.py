from rest_framework import serializers

from .models import Discount, Promo


class DiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discount
        fields = [
            "id", "name", "discount_type", "value",
            "is_active", "start_date", "end_date",
        ]


class PromoSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = Promo
        fields = [
            "id", "product", "product_name", "promo_price",
            "start_date", "end_date", "is_active",
        ]
