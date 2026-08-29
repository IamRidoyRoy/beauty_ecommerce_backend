from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class ShippingMethod(TimeStampedModel):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=50, unique=True)
    base_charge = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_days = models.CharField(max_length=80, blank=True)
    free_threshold = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    active = models.BooleanField(default=True, db_index=True)

    def charge_for(self, subtotal):
        return 0 if self.free_threshold is not None and subtotal >= self.free_threshold else self.base_charge


class CourierConfig(TimeStampedModel):
    class Provider(models.TextChoices):
        PATHAO = "pathao", "Pathao"
        STEADFAST = "steadfast", "Steadfast"
        REDX = "redx", "RedX"
        CARRYBEE = "carrybee", "CarryBee"

    provider = models.CharField(max_length=24, choices=Provider.choices, unique=True, db_index=True)
    display_name = models.CharField(max_length=80)
    is_active = models.BooleanField(default=False, db_index=True)
    sandbox_mode = models.BooleanField(default=True, help_text="Use provider sandbox when available.")
    sort_order = models.PositiveSmallIntegerField(default=0, db_index=True)
    auto_book_enabled = models.BooleanField(default=False, db_index=True)
    auto_book_order_status = models.CharField(max_length=30, default="packed")
    cancel_api_enabled = models.BooleanField(default=False, help_text="Enable provider-side cancellation only after the merchant API contract is verified.")
    sandbox_config_encrypted = models.TextField(blank=True, default="")
    live_config_encrypted = models.TextField(blank=True, default="")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_courier_configs",
    )

    class Meta:
        ordering = ("sort_order", "id")
        indexes = [models.Index(fields=["is_active", "sort_order"], name="courier_active_order_idx")]

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


class Shipment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        BOOKED = "booked", "Booked"
        PICKED = "picked", "Picked"
        IN_TRANSIT = "in_transit", "In Transit"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out For Delivery"
        DELIVERED = "delivered", "Delivered"
        RETURNED = "returned", "Returned"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class BookingSource(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTO = "auto", "Automatic"
        IMPORTED = "imported", "Imported"

    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="shipments")
    courier = models.CharField(max_length=30, blank=True, db_index=True)
    environment = models.CharField(max_length=12, blank=True, default="")
    external_id = models.CharField(max_length=120, blank=True, db_index=True)
    tracking_code = models.CharField(max_length=120, blank=True, db_index=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING, db_index=True)
    provider_status = models.CharField(max_length=120, blank=True, db_index=True)
    provider_message = models.TextField(blank=True)
    booking_source = models.CharField(max_length=16, choices=BookingSource.choices, default=BookingSource.MANUAL)
    booked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="booked_shipments",
    )
    payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    booked_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["courier", "status", "updated_at"], name="ship_courier_status_idx"),
            models.Index(fields=["order", "courier"], name="ship_order_courier_idx"),
        ]


class CourierEvent(TimeStampedModel):
    class Action(models.TextChoices):
        BOOK = "book", "Book"
        TRACK = "track", "Track"
        CANCEL = "cancel", "Cancel"
        WEBHOOK = "webhook", "Webhook"
        TEST = "test", "Test connection"

    shipment = models.ForeignKey(Shipment, null=True, blank=True, on_delete=models.CASCADE, related_name="events")
    provider = models.CharField(max_length=24, db_index=True)
    action = models.CharField(max_length=20, choices=Action.choices, db_index=True)
    success = models.BooleanField(default=False)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="courier_events",
    )

    class Meta:
        indexes = [models.Index(fields=["provider", "action", "created_at"], name="courier_event_lookup_idx")]


class CourierWebhookEvent(TimeStampedModel):
    shipment = models.ForeignKey(Shipment, null=True, blank=True, on_delete=models.SET_NULL, related_name="webhook_events")
    provider = models.CharField(max_length=24, db_index=True)
    event_id = models.CharField(max_length=180)
    payload = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_error = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "event_id"], name="unique_courier_webhook_event")]
        indexes = [models.Index(fields=["provider", "created_at"], name="courier_webhook_time_idx")]
