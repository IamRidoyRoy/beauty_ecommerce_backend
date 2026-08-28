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


class CheckoutSettings(TimeStampedModel):
    existing_customer_otp_verification = models.BooleanField(
        default=True,
        verbose_name="Existing customer OTP verification",
        help_text=(
            "When enabled, anonymous checkout with an existing phone requires OTP before account access. "
            "When disabled, development can auto-login that existing customer after a successful order."
        ),
    )

    class Meta:
        verbose_name = "Checkout setting"
        verbose_name_plural = "Checkout settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def current(cls):
        obj = cls.objects.filter(pk=1).only("existing_customer_otp_verification").first()
        return obj

    def __str__(self):
        return "Checkout settings"


class HeroSlide(TimeStampedModel):
    class TextPosition(models.TextChoices):
        LEFT = "left", "Left"
        CENTER = "center", "Center"
        RIGHT = "right", "Right"

    class Theme(models.TextChoices):
        LIGHT = "light", "Light text"
        DARK = "dark", "Dark text"

    eyebrow = models.CharField(max_length=120, blank=True)
    title = models.CharField(max_length=180)
    subtitle = models.TextField(blank=True)
    image = models.ImageField(upload_to="hero_slides/")
    mobile_image = models.ImageField(upload_to="hero_slides/mobile/", blank=True, null=True)
    image_alt = models.CharField(max_length=180, blank=True)

    primary_cta_label = models.CharField(max_length=80, blank=True)
    primary_cta_url = models.CharField(max_length=255, blank=True)
    secondary_cta_label = models.CharField(max_length=80, blank=True)
    secondary_cta_url = models.CharField(max_length=255, blank=True)

    text_position = models.CharField(max_length=12, choices=TextPosition.choices, default=TextPosition.LEFT)
    theme = models.CharField(max_length=12, choices=Theme.choices, default=Theme.DARK)
    overlay_opacity = models.PositiveSmallIntegerField(default=20, help_text="Background overlay opacity from 0 to 90 percent.")

    active = models.BooleanField(default=True, db_index=True)
    order = models.PositiveIntegerField(default=0, db_index=True)
    starts_at = models.DateTimeField(blank=True, null=True, db_index=True)
    ends_at = models.DateTimeField(blank=True, null=True, db_index=True)

    class Meta:
        ordering = ("order", "id")
        indexes = [models.Index(fields=("active", "order"))]

    def __str__(self):
        return self.title
