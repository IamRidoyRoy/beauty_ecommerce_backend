import uuid

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        COD = "cod", "COD"
        SSLCOMMERZ = "sslcommerz", "SSLCOMMERZ"
        BKASH = "bkash", "bKash"
        NAGAD = "nagad", "Nagad"
        CARD = "card", "Card (legacy / SSLCOMMERZ)"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        AUTHORIZED = "authorized", "Authorized"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        PARTIAL_REFUND = "partial_refund", "Partially Refunded"
        REFUNDED = "refunded", "Refunded"

    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="payments")
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    method = models.CharField(max_length=20, choices=Method.choices)
    currency = models.CharField(max_length=3, default="BDT")
    transaction_id = models.CharField(max_length=120, blank=True, db_index=True)
    gateway_reference = models.CharField(max_length=180, blank=True, db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING, db_index=True)
    initiated_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    failure_code = models.CharField(max_length=80, blank=True)
    failure_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["method", "status", "created_at"], name="pay_method_status_created_idx"),
            models.Index(fields=["order", "status"], name="pay_order_status_idx"),
        ]


class PaymentWebhookEvent(TimeStampedModel):
    payment = models.ForeignKey(Payment, null=True, blank=True, on_delete=models.SET_NULL, related_name="webhook_events")
    provider = models.CharField(max_length=30)
    event_id = models.CharField(max_length=180)
    payload = models.JSONField(default=dict)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_error = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "event_id"], name="unique_payment_webhook_event")]
        indexes = [models.Index(fields=["provider", "created_at"], name="pay_webhook_provider_time_idx")]


class PaymentReconciliation(TimeStampedModel):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="reconciliations")
    provider = models.CharField(max_length=30)
    previous_status = models.CharField(max_length=24, blank=True)
    gateway_status = models.CharField(max_length=80, blank=True)
    resolved_status = models.CharField(max_length=24, blank=True)
    success = models.BooleanField(default=False)
    response = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payment_reconciliations",
    )

class PaymentGatewayConfig(TimeStampedModel):
    class Provider(models.TextChoices):
        SSLCOMMERZ = "sslcommerz", "SSLCOMMERZ"
        BKASH = "bkash", "bKash"
        NAGAD = "nagad", "Nagad"

    provider = models.CharField(max_length=24, choices=Provider.choices, unique=True, db_index=True)
    display_name = models.CharField(max_length=80)
    is_active = models.BooleanField(default=False, db_index=True)
    sandbox_mode = models.BooleanField(default=True, help_text="When enabled, new payments use the sandbox/test environment.")
    sort_order = models.PositiveSmallIntegerField(default=0, db_index=True)
    sandbox_config_encrypted = models.TextField(blank=True, default="")
    live_config_encrypted = models.TextField(blank=True, default="")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_payment_gateway_configs",
    )

    class Meta:
        ordering = ("sort_order", "id")
        indexes = [models.Index(fields=["is_active", "sort_order"], name="pay_gateway_active_order_idx")]

    def __str__(self):
        return self.display_name or self.get_provider_display()

    @property
    def environment(self) -> str:
        return "sandbox" if self.sandbox_mode else "live"

    def get_environment_config(self, environment: str | None = None) -> dict:
        from .crypto import decrypt_json

        selected = environment or self.environment
        encrypted = self.sandbox_config_encrypted if selected == "sandbox" else self.live_config_encrypted
        return decrypt_json(encrypted)

    def set_environment_config(self, environment: str, values: dict) -> None:
        from .crypto import encrypt_json

        encrypted = encrypt_json(values)
        if environment == "sandbox":
            self.sandbox_config_encrypted = encrypted
        elif environment == "live":
            self.live_config_encrypted = encrypted
        else:
            raise ValueError("environment must be sandbox or live")

