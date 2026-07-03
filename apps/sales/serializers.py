from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from apps.catalog.models import Product
from apps.common.formatting import format_local_date, format_local_datetime

from .models import Payment, Sale, SaleItem, SaleItemVoidRequest
from .services import request_item_void


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
    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0.01")
    )
    tendered = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0.00"), required=False
    )

    class Meta:
        model = Payment
        fields = ["id", "method", "amount", "tendered", "reference"]

    def validate(self, attrs):
        # For cash, the tendered amount must at least cover the payment so
        # change can be computed; non-cash methods don't require tender.
        if attrs.get("method") == Payment.Method.CASH:
            tendered = attrs.get("tendered") or Decimal("0.00")
            if tendered < attrs["amount"]:
                raise serializers.ValidationError(
                    "Cash tendered must be at least the payment amount."
                )
        return attrs


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
    discount_name = serializers.CharField(source="discount.name", default=None, read_only=True)
    completed_at = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = [
            "id", "receipt_no", "cashier", "status", "discount", "discount_name",
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

    def validate_discount(self, discount):
        if discount and not discount.is_available():
            raise serializers.ValidationError("Selected discount is not active for today's date.")
        return discount

    def get_completed_at(self, obj):
        return format_local_datetime(obj.completed_at)

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

    def update(self, instance, validated_data):
        from .services import set_sale_items, recalculate_sale

        cart = validated_data.pop("cart", None)
        if instance.status != Sale.Status.DRAFT:
            raise serializers.ValidationError("Only draft sales can be updated.")

        if "discount" in validated_data:
            instance.discount = validated_data["discount"]
        if "note" in validated_data:
            instance.note = validated_data["note"]
        instance.save(update_fields=["discount", "note", "updated_at"])

        if cart is not None:
            return set_sale_items(instance, cart)
        return recalculate_sale(instance)


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
    date = serializers.SerializerMethodField()
    completed_at = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = [
            "receipt_no", "cashier", "completed_at", "date",
            "items", "subtotal", "discount_total", "total",
            "tax_label", "tax_rate", "tax_amount", "net_of_tax",
            "payments", "amount_paid", "change_due",
        ]

    def get_tax_label(self, obj):
        return settings.POS_TAX_LABEL

    def get_date(self, obj):
        """Return the receipt date (from completed_at)."""
        if obj.completed_at:
            return format_local_date(timezone.localtime(obj.completed_at).date())
        return None

    def get_completed_at(self, obj):
        return format_local_datetime(obj.completed_at)

class SaleItemVoidRequestCreateSerializer(serializers.Serializer):
    sale_item = serializers.IntegerField()
    quantity = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"), required=False,
        default=Decimal("1.00")
    )
    reason = serializers.CharField(max_length=255)

    def create(self, validated_data):
        sale_item = SaleItem.objects.select_related("sale", "product").get(pk=validated_data["sale_item"])
        request = self.context.get("request")
        return request_item_void(
            sale=sale_item.sale,
            sale_item_id=sale_item.pk,
            quantity=validated_data.get("quantity", Decimal("1.00")),
            reason=validated_data["reason"],
            user=getattr(request, "user", None),
        )


class SaleItemVoidRequestReviewSerializer(serializers.Serializer):
    review_note = serializers.CharField(max_length=255, required=False, allow_blank=True)


class SaleItemVoidRequestApproveSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    review_note = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.check_password(attrs["password"]):
            raise serializers.ValidationError({"password": "Admin password is incorrect."})
        return attrs


class SaleItemVoidRequestSerializer(serializers.ModelSerializer):
    requested_by = serializers.CharField(source="requested_by.username", read_only=True)
    reviewed_by = serializers.CharField(source="reviewed_by.username", read_only=True)

    class Meta:
        model = SaleItemVoidRequest
        fields = [
            "id", "sale", "sale_item_id", "product_sku", "product_name",
            "quantity", "reason", "status", "requested_by",
            "reviewed_by", "reviewed_at", "review_note", "created_at",
        ]
        read_only_fields = [
            "sale", "sale_item_id", "product_sku", "product_name", "status",
            "requested_by", "reviewed_by", "reviewed_at", "review_note", "created_at",
        ]
