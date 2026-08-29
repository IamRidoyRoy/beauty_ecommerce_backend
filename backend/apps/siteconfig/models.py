from django.db import models


class SiteBrandingSettings(models.Model):
    class BrandMode(models.TextChoices):
        TEXT = "text", "Text name"
        LOGO = "logo", "Logo image"

    website_brand_mode = models.CharField(max_length=8, choices=BrandMode.choices, default=BrandMode.TEXT)
    website_name = models.CharField(max_length=120, default="LUMÉA")
    website_tagline = models.CharField(max_length=160, default="Beauty Commerce", blank=True)
    website_logo = models.ImageField(upload_to="branding/website/", blank=True, null=True)

    dashboard_brand_mode = models.CharField(max_length=8, choices=BrandMode.choices, default=BrandMode.TEXT)
    dashboard_name = models.CharField(max_length=120, default="BEAUTYOPS")
    dashboard_tagline = models.CharField(max_length=160, default="Commerce Control", blank=True)
    dashboard_logo = models.ImageField(upload_to="branding/dashboard/", blank=True, null=True)

    primary_color = models.CharField(max_length=7, default="#d43a89")
    secondary_color = models.CharField(max_length=7, default="#33245e")
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Site branding setting"
        verbose_name_plural = "Site branding settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def current(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Website & dashboard branding"


class HomepageBanner(models.Model):
    class Slot(models.TextChoices):
        PROMO_LEFT = "promo_left", "Promo banner — left"
        PROMO_RIGHT = "promo_right", "Promo banner — right"
        EDITORIAL = "editorial", "Editorial / ingredient spotlight"

    class LinkType(models.TextChoices):
        NONE = "none", "No link"
        CUSTOM = "custom", "Custom route / URL"
        PRODUCTS = "products", "Products page"
        CATEGORY = "category", "Category"
        BRAND = "brand", "Brand"
        PRODUCT = "product", "Product"
        SEARCH = "search", "Search query"

    slot = models.CharField(max_length=32, choices=Slot.choices, unique=True)
    eyebrow = models.CharField(max_length=120, blank=True)
    title = models.CharField(max_length=220)
    subtitle = models.TextField(blank=True)
    cta_label = models.CharField(max_length=80, blank=True)

    link_type = models.CharField(max_length=16, choices=LinkType.choices, default=LinkType.NONE)
    link_value = models.CharField(max_length=500, blank=True, help_text="Slug, query, or custom route depending on link type.")

    image = models.ImageField(upload_to="homepage/banners/", blank=True, null=True)
    image_alt = models.CharField(max_length=180, blank=True)
    background_color = models.CharField(max_length=7, default="#3f3272")
    text_color = models.CharField(max_length=7, default="#ffffff")
    media_background_color = models.CharField(max_length=7, default="#ead7d2")
    active = models.BooleanField(default=True, db_index=True)

    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("slot",)
        verbose_name = "Homepage banner"
        verbose_name_plural = "Homepage banners"

    def __str__(self):
        return f"{self.get_slot_display()}: {self.title}"


class AnnouncementItem(models.Model):
    class Icon(models.TextChoices):
        GIFT = "gift", "Gift"
        BADGE = "badge", "Authenticity badge"
        TRUCK = "truck", "Delivery truck"
        SPARKLES = "sparkles", "Sparkles"
        TAG = "tag", "Offer tag"

    class LinkType(models.TextChoices):
        NONE = "none", "No link"
        CUSTOM = "custom", "Custom route / URL"
        PRODUCTS = "products", "Products page"
        CATEGORY = "category", "Category"
        BRAND = "brand", "Brand"
        PRODUCT = "product", "Product"
        SEARCH = "search", "Search query"

    text = models.CharField(max_length=220)
    icon = models.CharField(max_length=16, choices=Icon.choices, default=Icon.SPARKLES)
    link_type = models.CharField(max_length=16, choices=LinkType.choices, default=LinkType.NONE)
    link_value = models.CharField(max_length=500, blank=True)
    active = models.BooleanField(default=True, db_index=True)
    order = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "id")

    def __str__(self):
        return self.text
