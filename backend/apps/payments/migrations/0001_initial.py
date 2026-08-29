# Baseline migration for the payment schema that existed before the gateway upgrade.
# Existing installations should fake-apply this migration once, then apply 0002 normally.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("cod", "COD"),
                            ("bkash", "bKash"),
                            ("nagad", "Nagad"),
                            ("card", "Card"),
                        ],
                        max_length=20,
                    ),
                ),
                ("transaction_id", models.CharField(blank=True, db_index=True, max_length=120)),
                ("gateway_reference", models.CharField(blank=True, db_index=True, max_length=180)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("authorized", "Authorized"),
                            ("paid", "Paid"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                            ("partial_refund", "Partially Refunded"),
                            ("refunded", "Refunded"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=24,
                    ),
                ),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to="orders.order",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PaymentWebhookEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("provider", models.CharField(max_length=30)),
                ("event_id", models.CharField(max_length=180)),
                ("payload", models.JSONField(default=dict)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("processing_error", models.TextField(blank=True)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("provider", "event_id"),
                        name="unique_payment_webhook_event",
                    )
                ]
            },
        ),
    ]
