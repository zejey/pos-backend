from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0002_sale_tax_amount_sale_tax_rate"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SaleItemVoidRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sale_item_id", models.PositiveBigIntegerField()),
                ("product_sku", models.CharField(max_length=64)),
                ("product_name", models.CharField(max_length=255)),
                ("quantity", models.DecimalField(decimal_places=2, max_digits=12)),
                ("reason", models.CharField(max_length=255)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("APPROVED", "Approved"), ("DENIED", "Denied")], default="PENDING", max_length=10)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_note", models.CharField(blank=True, max_length=255)),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sale_item_void_requests", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_sale_item_void_requests", to=settings.AUTH_USER_MODEL)),
                ("sale", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="item_void_requests", to="sales.sale")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="saleitemvoidrequest",
            index=models.Index(fields=["status", "-created_at"], name="sales_itemv_status_d1b6e0_idx"),
        ),
        migrations.AddIndex(
            model_name="saleitemvoidrequest",
            index=models.Index(fields=["sale", "status"], name="sales_itemv_sale_3b7405_idx"),
        ),
    ]