from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_gateway_configs(apps, schema_editor):
    Gateway = apps.get_model("payments", "PaymentGatewayConfig")
    rows = (
        ("sslcommerz", "SSLCOMMERZ", 10),
        ("bkash", "bKash", 20),
        ("nagad", "Nagad", 30),
    )
    for provider, display_name, sort_order in rows:
        Gateway.objects.get_or_create(
            provider=provider,
            defaults={
                "display_name": display_name,
                "is_active": False,
                "sandbox_mode": True,
                "sort_order": sort_order,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0002_gateway_upgrade"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentGatewayConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("provider", models.CharField(choices=[("sslcommerz", "SSLCOMMERZ"), ("bkash", "bKash"), ("nagad", "Nagad")], db_index=True, max_length=24, unique=True)),
                ("display_name", models.CharField(max_length=80)),
                ("is_active", models.BooleanField(db_index=True, default=False)),
                ("sandbox_mode", models.BooleanField(default=True, help_text="When enabled, new payments use the sandbox/test environment.")),
                ("sort_order", models.PositiveSmallIntegerField(db_index=True, default=0)),
                ("sandbox_config_encrypted", models.TextField(blank=True, default="")),
                ("live_config_encrypted", models.TextField(blank=True, default="")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_payment_gateway_configs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("sort_order", "id")},
        ),
        migrations.AddIndex(
            model_name="paymentgatewayconfig",
            index=models.Index(fields=["is_active", "sort_order"], name="pay_gateway_active_order_idx"),
        ),
        migrations.RunPython(seed_gateway_configs, migrations.RunPython.noop),
    ]
