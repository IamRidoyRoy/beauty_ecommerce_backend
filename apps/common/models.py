import uuid
from django.conf import settings
from django.db import models

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class UUIDModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    class Meta:
        abstract = True

class AnalyticsEvent(TimeStampedModel):
    class EventType(models.TextChoices):
        PRODUCT_VIEW = "product_view", "Product View"
        ADD_TO_CART = "add_to_cart", "Add To Cart"
        WISHLIST = "wishlist", "Wishlist"
        CHECKOUT_STARTED = "checkout_started", "Checkout Started"
        ORDER_COMPLETED = "order_completed", "Order Completed"
    event_type = models.CharField(max_length=32, choices=EventType.choices, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="analytics_events")
    session_token = models.CharField(max_length=128, blank=True, db_index=True)
    cart_token = models.CharField(max_length=128, blank=True, db_index=True)
    product_id_ref = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    class Meta:
        indexes = [models.Index(fields=["event_type", "created_at"]), models.Index(fields=["product_id_ref", "created_at"])]
