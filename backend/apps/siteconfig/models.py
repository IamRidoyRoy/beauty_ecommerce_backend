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
