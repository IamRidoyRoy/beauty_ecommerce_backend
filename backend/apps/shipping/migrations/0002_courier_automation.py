from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_couriers(apps, schema_editor):
    CourierConfig = apps.get_model("shipping", "CourierConfig")
    for provider, display_name, sort_order, sandbox in (
        ("pathao", "Pathao", 10, True),
        ("steadfast", "Steadfast", 20, False),
        ("redx", "RedX", 30, True),
    ):
        CourierConfig.objects.get_or_create(provider=provider, defaults={"display_name": display_name, "sort_order": sort_order, "sandbox_mode": sandbox, "is_active": False})


class Migration(migrations.Migration):
    dependencies = [
        ("shipping", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AlterField(
            model_name="shipment",
            name="courier",
            field=models.CharField(blank=True, db_index=True, max_length=30),
        ),
        migrations.AlterField(
            model_name="shipment",
            name="status",
            field=models.CharField(choices=[("pending", "Pending"), ("booked", "Booked"), ("picked", "Picked"), ("in_transit", "In Transit"), ("out_for_delivery", "Out For Delivery"), ("delivered", "Delivered"), ("returned", "Returned"), ("failed", "Failed"), ("cancelled", "Cancelled")], db_index=True, default="pending", max_length=24),
        ),
        migrations.AddField(model_name="shipment", name="environment", field=models.CharField(blank=True, default="", max_length=12)),
        migrations.AddField(model_name="shipment", name="provider_status", field=models.CharField(blank=True, db_index=True, max_length=120)),
        migrations.AddField(model_name="shipment", name="provider_message", field=models.TextField(blank=True)),
        migrations.AddField(model_name="shipment", name="booking_source", field=models.CharField(choices=[("manual", "Manual"), ("auto", "Automatic"), ("imported", "Imported")], default="manual", max_length=16)),
        migrations.AddField(model_name="shipment", name="last_synced_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="shipment", name="booked_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="shipment", name="picked_up_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="shipment", name="dispatched_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="shipment", name="delivered_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="shipment", name="cancelled_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="shipment", name="booked_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="booked_shipments", to=settings.AUTH_USER_MODEL)),
        migrations.CreateModel(
            name="CourierConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("provider", models.CharField(choices=[("pathao", "Pathao"), ("steadfast", "Steadfast"), ("redx", "RedX")], db_index=True, max_length=24, unique=True)),
                ("display_name", models.CharField(max_length=80)),
                ("is_active", models.BooleanField(db_index=True, default=False)),
                ("sandbox_mode", models.BooleanField(default=True, help_text="Use provider sandbox when available.")),
                ("sort_order", models.PositiveSmallIntegerField(db_index=True, default=0)),
                ("auto_book_enabled", models.BooleanField(db_index=True, default=False)),
                ("auto_book_order_status", models.CharField(default="packed", max_length=30)),
                ("cancel_api_enabled", models.BooleanField(default=False, help_text="Enable provider-side cancellation only after the merchant API contract is verified.")),
                ("sandbox_config_encrypted", models.TextField(blank=True, default="")),
                ("live_config_encrypted", models.TextField(blank=True, default="")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_courier_configs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("sort_order", "id")},
        ),
        migrations.CreateModel(
            name="CourierEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("provider", models.CharField(db_index=True, max_length=24)),
                ("action", models.CharField(choices=[("book", "Book"), ("track", "Track"), ("cancel", "Cancel"), ("webhook", "Webhook"), ("test", "Test connection")], db_index=True, max_length=20)),
                ("success", models.BooleanField(default=False)),
                ("request_payload", models.JSONField(blank=True, default=dict)),
                ("response_payload", models.JSONField(blank=True, default=dict)),
                ("error", models.TextField(blank=True)),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="courier_events", to=settings.AUTH_USER_MODEL)),
                ("shipment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="events", to="shipping.shipment")),
            ],
        ),
        migrations.CreateModel(
            name="CourierWebhookEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("provider", models.CharField(db_index=True, max_length=24)),
                ("event_id", models.CharField(max_length=180)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("processing_error", models.TextField(blank=True)),
                ("shipment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="webhook_events", to="shipping.shipment")),
            ],
        ),
        migrations.AddIndex(model_name="courierconfig", index=models.Index(fields=["is_active", "sort_order"], name="courier_active_order_idx")),
        migrations.AddIndex(model_name="shipment", index=models.Index(fields=["courier", "status", "updated_at"], name="ship_courier_status_idx")),
        migrations.AddIndex(model_name="shipment", index=models.Index(fields=["order", "courier"], name="ship_order_courier_idx")),
        migrations.AddIndex(model_name="courierevent", index=models.Index(fields=["provider", "action", "created_at"], name="courier_event_lookup_idx")),
        migrations.AddConstraint(model_name="courierwebhookevent", constraint=models.UniqueConstraint(fields=("provider", "event_id"), name="unique_courier_webhook_event")),
        migrations.AddIndex(model_name="courierwebhookevent", index=models.Index(fields=["provider", "created_at"], name="courier_webhook_time_idx")),
        migrations.RunPython(seed_couriers, migrations.RunPython.noop),
    ]
