# Baseline migration for the shipping schema that existed before courier automation.
# Existing installations should fake-apply this migration once, then apply 0002 normally.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="ShippingMethod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120)),
                ("code", models.CharField(max_length=50, unique=True)),
                ("base_charge", models.DecimalField(decimal_places=2, max_digits=10)),
                ("estimated_days", models.CharField(blank=True, max_length=80)),
                ("free_threshold", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("active", models.BooleanField(db_index=True, default=True)),
            ],
        ),
        migrations.CreateModel(
            name="Shipment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("courier", models.CharField(blank=True, max_length=30)),
                ("external_id", models.CharField(blank=True, db_index=True, max_length=120)),
                ("tracking_code", models.CharField(blank=True, db_index=True, max_length=120)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("booked", "Booked"), ("picked", "Picked"), ("in_transit", "In Transit"), ("delivered", "Delivered"), ("failed", "Failed"), ("cancelled", "Cancelled")], default="pending", max_length=20)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shipments", to="orders.order")),
            ],
        ),
    ]
