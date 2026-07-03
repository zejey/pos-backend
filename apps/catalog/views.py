import csv
from decimal import Decimal, InvalidOperation
from io import StringIO

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

    @action(detail=False, methods=["post"], url_path="import-csv")
    def import_csv(self, request):
        """Import product master data from a CSV upload."""
        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"detail": "A 'file' upload is required.", "code": "required"},
                status=400,
            )

        try:
            text = upload.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return Response(
                {"detail": "The CSV file must be UTF-8 encoded.", "code": "invalid_csv"},
                status=400,
            )

        reader = csv.DictReader(StringIO(text))
        if not reader.fieldnames:
            return Response(
                {"detail": "The CSV file is missing a header row.", "code": "invalid_csv"},
                status=400,
            )

        products = []
        errors = []
        seen_skus = set()
        category_cache = {}

        def parse_decimal(raw_value, field_name, row_number, default=None):
            value = (raw_value or "").strip()
            if not value:
                return default
            try:
                return Decimal(value)
            except (InvalidOperation, TypeError):
                errors.append({
                    "row": row_number,
                    "field": field_name,
                    "detail": f"Invalid decimal value: {value}",
                })
                return default

        def parse_bool(raw_value, default=True):
            value = (raw_value or "").strip().lower()
            if not value:
                return default
            if value in {"1", "true", "yes", "y"}:
                return True
            if value in {"0", "false", "no", "n"}:
                return False
            return default

        for row_number, row in enumerate(reader, start=2):
            if not any((value or "").strip() for value in row.values()):
                continue

            name = (row.get("name") or "").strip()
            sku = (row.get("sku") or "").strip()
            barcode = (row.get("barcode") or "").strip()
            unit = (row.get("unit") or "pc").strip() or "pc"
            category_raw = (row.get("category") or "").strip()

            if not name:
                errors.append({
                    "row": row_number,
                    "field": "name",
                    "detail": "This field is required.",
                })
                continue

            if sku:
                if sku in seen_skus:
                    errors.append({
                        "row": row_number,
                        "field": "sku",
                        "detail": "Duplicate SKU in CSV file.",
                    })
                    continue
                if Product.objects.filter(sku=sku).exists():
                    errors.append({
                        "row": row_number,
                        "field": "sku",
                        "detail": "SKU already exists.",
                    })
                    continue
                seen_skus.add(sku)

            category = None
            if category_raw:
                if category_raw.isdigit():
                    category = category_cache.get(("id", category_raw))
                    if category is None:
                        category = Category.objects.filter(pk=category_raw).first()
                        if category is not None:
                            category_cache[("id", category_raw)] = category
                else:
                    cache_key = ("name", category_raw.lower())
                    category = category_cache.get(cache_key)
                    if category is None:
                        category = Category.objects.filter(name__iexact=category_raw).first()
                        if category is not None:
                            category_cache[cache_key] = category

                if category is None:
                    errors.append({
                        "row": row_number,
                        "field": "category",
                        "detail": f"Category not found: {category_raw}",
                    })
                    continue

            cost_price = parse_decimal(row.get("cost_price"), "cost_price", row_number, Decimal("0.00"))
            selling_price = parse_decimal(row.get("selling_price"), "selling_price", row_number, Decimal("0.00"))
            reorder_level = parse_decimal(row.get("reorder_level"), "reorder_level", row_number, Decimal("5.00"))

            if any(error.get("row") == row_number for error in errors):
                continue

            product_kwargs = {
                "barcode": barcode,
                "name": name,
                "category": category,
                "unit": unit,
                "cost_price": cost_price,
                "selling_price": selling_price,
                "reorder_level": reorder_level,
                "is_active": parse_bool(row.get("is_active"), True),
            }
            if sku:
                product_kwargs["sku"] = sku
            products.append(Product(**product_kwargs))

        if errors:
            return Response(
                {"detail": "Validation failed.", "code": "validation_error", "errors": errors},
                status=400,
            )

        created = Product.objects.bulk_create(products)
        log_activity(
            request.user,
            "PRODUCT_CSV_IMPORT",
            entity="Product",
            detail={"count": len(created)},
            request=request,
        )
        return Response(
            {"created": len(created), "products": ProductSerializer(created, many=True).data},
            status=201,
        )

    @action(detail=False, methods=["get"], url_path="by-barcode")
    def by_barcode(self, request):
        """Look up a single active product by exact barcode (FEAT-04).

        Powers fast cashier scanning: GET /catalog/products/by-barcode/?barcode=...
        """
        barcode = request.query_params.get("barcode", "").strip()
        if not barcode:
            return Response({"detail": "A 'barcode' query parameter is required.",
                             "code": "required"}, status=400)
        product = (
            Product.objects.filter(barcode=barcode, is_active=True)
            .select_related("category").first()
        )
        if product is None:
            return Response({"detail": "No active product with that barcode.",
                             "code": "not_found"}, status=404)
        return Response(ProductSerializer(product).data)
