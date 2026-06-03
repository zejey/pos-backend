from decimal import Decimal

from django.conf import settings
from rest_framework import serializers

from apps.catalog.models import Product

from .models import Payment, Sale, SaleItem


class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)

    class Meta:
        model = SaleItem
        fields = [
            "id", "product", "product_sku", "product_name",
            "quantity", "unit_price", "line_total",
        ]
        read_only_fields = ["unit_price", "line_total"]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "method", "amount", "tendered", "reference"]


class CartItemInputSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )


class SaleSerializer(serializers.ModelSerializer):
    """Read + create-cart serializer for sales."""

    items = SaleItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    cart = CartItemInputSerializer(many=True, write_only=True, required=False)
    cashier = serializers.CharField(source="cashier.username", default=None, read_only=True)
    amount_paid = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    change_due = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    net_of_tax = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id", "receipt_no", "cashier", "status", "discount",
            "subtotal", "discount_total", "total",
            "tax_rate", "tax_amount", "net_of_tax",
            "amount_paid", "change_due", "note",
            "items", "payments", "cart",
            "completed_at", "voided_at", "void_reason", "created_at",
        ]
        read_only_fields = [
            "receipt_no", "status", "subtotal", "discount_total", "total",
            "tax_rate", "tax_amount",
            "completed_at", "voided_at", "void_reason",
        ]

    def create(self, validated_data):
        from .services import current_tax_rate, set_sale_items

        cart = validated_data.pop("cart", [])
        request = self.context.get("request")
        sale = Sale.objects.create(
            cashier=getattr(request, "user", None),
            discount=validated_data.get("discount"),
            note=validated_data.get("note", ""),
            tax_rate=current_tax_rate(),  # snapshot at creation
        )
        if cart:
            set_sale_items(sale, cart)
        return sale


class CompleteSaleSerializer(serializers.Serializer):
    payments = PaymentSerializer(many=True)


class VoidSaleSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class ReceiptSerializer(serializers.ModelSerializer):
    """Structured receipt payload the frontend renders/prints (POS 1.5)."""

    items = SaleItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    cashier = serializers.CharField(source="cashier.username", default=None, read_only=True)
    amount_paid = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    change_due = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    net_of_tax = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    tax_label = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = [
            "receipt_no", "cashier", "completed_at",
            "items", "subtotal", "discount_total", "total",
            "tax_label", "tax_rate", "tax_amount", "net_of_tax",
            "payments", "amount_paid", "change_due",
        ]

    def get_tax_label(self, obj):
        return settings.POS_TAX_LABEL
