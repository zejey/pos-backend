import csv
from collections import OrderedDict
from datetime import date
from decimal import Decimal, InvalidOperation
from io import StringIO

from django.db import transaction
from django.utils.dateparse import parse_date
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.services import log_activity
from apps.catalog.models import Product
from apps.common.mixins import ActivityLogMixin
from apps.common.permissions import IsAdmin

from .models import StockIn, StockInItem, Supplier
from .serializers import StockInSerializer, SupplierSerializer
from .services import post_stock_in


class SupplierViewSet(ActivityLogMixin, viewsets.ModelViewSet):
    """Suppliers / vendors. Admin only."""

    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAdmin]
    filterset_fields = ["is_active"]
    search_fields = ["name", "contact_person", "contact_no"]
    ordering_fields = ["name", "created_at"]


class StockInViewSet(viewsets.ModelViewSet):
    """Stock-in / purchase documents. Admin only."""

    queryset = (
        StockIn.objects.select_related("supplier")
        .prefetch_related("items__product")
        .all()
    )
    serializer_class = StockInSerializer
    permission_classes = [IsAdmin]
    filterset_fields = ["status", "supplier"]
    search_fields = ["reference_no", "supplier__name"]
    ordering_fields = ["purchase_date", "created_at"]

    def perform_create(self, serializer):
        stock_in = serializer.save(created_by=self.request.user)
        discrepancy_count = sum(1 for item in stock_in.items.all() if item.discrepancy_qty)
        log_activity(self.request.user, "STOCKIN_CREATE", entity="StockIn",
                     entity_id=stock_in.pk,
                     detail={
                         "reference_no": stock_in.reference_no,
                         "items": stock_in.items.count(),
                         "discrepancies": discrepancy_count,
                     },
                     request=self.request)

    @action(detail=True, methods=["post"])
    def post_document(self, request, pk=None):
        """Post the stock-in: received quantities flow into inventory."""
        stock_in = self.get_object()
        post_stock_in(stock_in, user=request.user)
        discrepancy_count = sum(1 for item in stock_in.items.all() if item.discrepancy_qty)
        log_activity(request.user, "STOCKIN_POST", entity="StockIn",
                     entity_id=stock_in.pk,
                     detail={
                         "reference_no": stock_in.reference_no,
                         "items": stock_in.items.count(),
                         "discrepancies": discrepancy_count,
                         "total_cost": str(stock_in.total_cost),
                     },
                     request=request)
        return Response(self.get_serializer(stock_in).data)

    @action(detail=False, methods=["post"], url_path="import-csv")
    def import_csv(self, request):
        """Import draft stock-in documents from a CSV upload.

        Expected columns:
        reference_no, purchase_date, supplier, note, product, quantity_ordered,
        quantity_received, unit_cost, discrepancy_reason
        """
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

        required_columns = {"reference_no", "purchase_date", "product", "quantity_ordered", "quantity_received", "unit_cost"}
        missing_columns = [column for column in required_columns if column not in reader.fieldnames]
        if missing_columns:
            return Response(
                {
                    "detail": "The CSV file is missing required columns.",
                    "code": "invalid_csv",
                    "errors": {"columns": missing_columns},
                },
                status=400,
            )

        def parse_decimal(raw_value, field_name, row_number, minimum=None, allow_blank=False):
            value = (raw_value or "").strip()
            if not value:
                if allow_blank:
                    return None
                raise ValueError(f"{field_name} is required.")
            try:
                parsed = Decimal(value)
            except (InvalidOperation, TypeError):
                raise ValueError(f"Invalid decimal value for {field_name}: {value}")
            if minimum is not None and parsed < minimum:
                raise ValueError(f"{field_name} must be greater than or equal to {minimum}.")
            return parsed

        def resolve_supplier(raw_value):
            value = (raw_value or "").strip()
            if not value:
                return None
            if value.isdigit():
                supplier = Supplier.objects.filter(pk=value).first()
                if supplier is not None:
                    return supplier
            return Supplier.objects.filter(name__iexact=value).first()

        def resolve_product(raw_value):
            value = (raw_value or "").strip()
            if not value:
                return None
            if value.isdigit():
                product = Product.objects.filter(pk=value).first()
                if product is not None:
                    return product
            product = Product.objects.filter(sku=value).first()
            if product is not None:
                return product
            return Product.objects.filter(name__iexact=value).first()

        grouped_rows = OrderedDict()
        errors = []

        for row_number, row in enumerate(reader, start=2):
            if not any((value or "").strip() for value in row.values()):
                continue

            reference_no = (row.get("reference_no") or "").strip()
            if not reference_no:
                errors.append({"row": row_number, "field": "reference_no", "detail": "This field is required."})
                continue

            purchase_date = parse_date((row.get("purchase_date") or "").strip())
            if purchase_date is None:
                errors.append({"row": row_number, "field": "purchase_date", "detail": "Use YYYY-MM-DD."})
                continue

            supplier = resolve_supplier(row.get("supplier"))
            supplier_raw = (row.get("supplier") or "").strip()
            if supplier_raw and supplier is None:
                errors.append({"row": row_number, "field": "supplier", "detail": f"Supplier not found: {supplier_raw}"})
                continue

            product = resolve_product(row.get("product"))
            product_raw = (row.get("product") or "").strip()
            if product_raw and product is None:
                errors.append({"row": row_number, "field": "product", "detail": f"Product not found: {product_raw}"})
                continue

            if product is None:
                errors.append({"row": row_number, "field": "product", "detail": "This field is required."})
                continue

            try:
                quantity_ordered = parse_decimal(row.get("quantity_ordered"), "quantity_ordered", row_number, minimum=Decimal("0.01"))
                quantity_received = parse_decimal(row.get("quantity_received"), "quantity_received", row_number, minimum=Decimal("0.00"))
                unit_cost = parse_decimal(row.get("unit_cost"), "unit_cost", row_number, minimum=Decimal("0.00"))
            except ValueError as exc:
                errors.append({"row": row_number, "field": "line", "detail": str(exc)})
                continue

            discrepancy_reason = (row.get("discrepancy_reason") or "").strip()
            if quantity_received != quantity_ordered and not discrepancy_reason:
                errors.append({
                    "row": row_number,
                    "field": "discrepancy_reason",
                    "detail": "A discrepancy_reason is required when received quantity differs from ordered quantity.",
                })
                continue

            group = grouped_rows.setdefault(reference_no, {
                "reference_no": reference_no,
                "purchase_date": purchase_date,
                "supplier": supplier,
                "note": (row.get("note") or "").strip(),
                "items": [],
            })

            if group["purchase_date"] != purchase_date:
                errors.append({"row": row_number, "field": "purchase_date", "detail": "Rows with the same reference_no must share the same purchase_date."})
                continue
            if group["supplier"] != supplier:
                errors.append({"row": row_number, "field": "supplier", "detail": "Rows with the same reference_no must share the same supplier."})
                continue
            note = (row.get("note") or "").strip()
            if group["note"] != note:
                errors.append({"row": row_number, "field": "note", "detail": "Rows with the same reference_no must share the same note."})
                continue

            group["items"].append({
                "product": product,
                "quantity_ordered": quantity_ordered,
                "quantity_received": quantity_received,
                "unit_cost": unit_cost,
                "discrepancy_reason": discrepancy_reason,
            })

        if errors:
            return Response(
                {"detail": "Validation failed.", "code": "validation_error", "errors": errors},
                status=400,
            )

        duplicate_refs = [
            reference_no for reference_no in grouped_rows
            if StockIn.objects.filter(reference_no=reference_no).exists()
        ]
        if duplicate_refs:
            return Response(
                {
                    "detail": "One or more stock-in references already exist.",
                    "code": "duplicate",
                    "errors": {"reference_no": duplicate_refs},
                },
                status=400,
            )

        created_stock_ins = []
        with transaction.atomic():
            for group in grouped_rows.values():
                stock_in = StockIn.objects.create(
                    reference_no=group["reference_no"],
                    supplier=group["supplier"],
                    purchase_date=group["purchase_date"],
                    note=group["note"],
                    created_by=request.user,
                )
                StockInItem.objects.bulk_create([
                    StockInItem(stock_in=stock_in, **item) for item in group["items"]
                ])
                created_stock_ins.append(stock_in)

        log_activity(
            request.user,
            "STOCKIN_CSV_IMPORT",
            entity="StockIn",
            detail={"count": len(created_stock_ins)},
            request=request,
        )
        return Response(
            {
                "created": len(created_stock_ins),
                "stock_ins": StockInSerializer(created_stock_ins, many=True).data,
            },
            status=201,
        )
