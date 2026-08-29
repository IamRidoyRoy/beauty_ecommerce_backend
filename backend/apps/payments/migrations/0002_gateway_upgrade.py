import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def populate_public_tokens(apps, schema_editor):
    """Give every existing payment a different token before making it UNIQUE."""
    Payment = apps.get_model("payments", "Payment")
    for payment_id in Payment.objects.filter(public_token__isnull=True).values_list("pk", flat=True).iterator():
        Payment.objects.filter(pk=payment_id).update(public_token=uuid.uuid4())


def reverse_public_tokens(apps, schema_editor):
    # Nothing needs to be restored when rolling back to the legacy schema.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="payment",
            name="method",
            field=models.CharField(
                choices=[
                    ("cod", "COD"),
                    ("sslcommerz", "SSLCOMMERZ"),
                    ("bkash", "bKash"),
                    ("nagad", "Nagad"),
                    ("card", "Card (legacy / SSLCOMMERZ)"),
                ],
                max_length=20,
            ),
        ),
        # Add nullable/non-unique first so existing rows can be populated safely.
        migrations.AddField(
            model_name="payment",
            name="public_token",
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.RunPython(populate_public_tokens, reverse_public_tokens),
        migrations.AlterField(
            model_name="payment",
            name="public_token",
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="currency",
            field=models.CharField(default="BDT", max_length=3),
        ),
        migrations.AddField(
            model_name="payment",
            name="initiated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="last_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="failure_code",
            field=models.CharField(blank=True, default="", max_length=80),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="payment",
            name="failure_message",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="paymentwebhookevent",
            name="payment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="webhook_events",
                to="payments.payment",
            ),
        ),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(fields=["method", "status", "created_at"], name="pay_method_status_created_idx"),
        ),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(fields=["order", "status"], name="pay_order_status_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentwebhookevent",
            index=models.Index(fields=["provider", "created_at"], name="pay_webhook_provider_time_idx"),
        ),
        migrations.CreateModel(
            name="PaymentReconciliation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("provider", models.CharField(max_length=30)),
                ("previous_status", models.CharField(blank=True, max_length=24)),
                ("gateway_status", models.CharField(blank=True, max_length=80)),
                ("resolved_status", models.CharField(blank=True, max_length=24)),
                ("success", models.BooleanField(default=False)),
                ("response", models.JSONField(blank=True, default=dict)),
                ("error", models.TextField(blank=True)),
                (
                    "payment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reconciliations",
                        to="payments.payment",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="payment_reconciliations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
