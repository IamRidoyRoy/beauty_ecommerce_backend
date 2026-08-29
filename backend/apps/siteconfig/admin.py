from django.contrib import admin
from .models import SiteBrandingSettings


@admin.register(SiteBrandingSettings)
class SiteBrandingSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Website branding", {"fields": ("website_brand_mode", "website_name", "website_tagline", "website_logo")}),
        ("Dashboard branding", {"fields": ("dashboard_brand_mode", "dashboard_name", "dashboard_tagline", "dashboard_logo")}),
        ("Website theme", {"fields": ("primary_color", "secondary_color")}),
    )

    def has_add_permission(self, request):
        return not SiteBrandingSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
