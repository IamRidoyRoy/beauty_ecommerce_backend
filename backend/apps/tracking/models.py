from django.db import models

from apps.common.models import TimeStampedModel


DEFAULT_TRACKING_EVENTS = {
    "PageView": True,
    "ViewContent": True,
    "Search": True,
    "AddToCart": True,
    "AddToWishlist": True,
    "InitiateCheckout": True,
    "Purchase": True,
}


def default_tracking_events():
    return dict(DEFAULT_TRACKING_EVENTS)


class TrackingSettings(TimeStampedModel):
    """Singleton marketing-tracking configuration controlled from BEAUTYOPS."""

    enabled = models.BooleanField(default=False)
    browser_tracking_enabled = models.BooleanField(default=True)
    server_tracking_enabled = models.BooleanField(default=True)
    require_marketing_consent = models.BooleanField(
        default=False,
        help_text="When enabled, storefront events must carry marketing consent before browser/server tracking is sent.",
    )

    gtm_container_id = models.CharField(max_length=40, blank=True)
    meta_pixel_id = models.CharField(max_length=64, blank=True)
    meta_api_version = models.CharField(max_length=16, default="v26.0")
    meta_access_token_encrypted = models.TextField(blank=True)
    meta_test_event_code = models.CharField(max_length=120, blank=True)
    currency = models.CharField(max_length=8, default="BDT")
    enabled_events = models.JSONField(default=default_tracking_events, blank=True)

    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(max_length=20, blank=True)
    last_test_message = models.TextField(blank=True)

    class Meta:
        verbose_name = "Tracking setting"
        verbose_name_plural = "Tracking settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def current(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def event_enabled(self, event_name: str) -> bool:
        values = self.enabled_events or {}
        return bool(values.get(event_name, True))

    def __str__(self):
        return "Tracking settings"


class TrackingEventLog(TimeStampedModel):
    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    event_name = models.CharField(max_length=64, db_index=True)
    event_id = models.CharField(max_length=160, db_index=True)
    source = models.CharField(max_length=32, default="server")
    status = models.CharField(max_length=16, choices=Status.choices, db_index=True)
    user_id_ref = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    order_number = models.CharField(max_length=80, blank=True, db_index=True)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    custom_data = models.JSONField(default=dict, blank=True)
    response_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("event_name", "created_at")),
            models.Index(fields=("status", "created_at")),
        ]

    def __str__(self):
        return f"{self.event_name} · {self.status}"
