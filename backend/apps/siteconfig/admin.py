from django.contrib import admin
from .models import HomepageBanner, SiteBrandingSettings


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


@admin.register(HomepageBanner)
class HomepageBannerAdmin(admin.ModelAdmin):
    list_display = ("slot", "title", "link_type", "active", "updated_at")
    list_filter = ("active", "slot", "link_type")
    search_fields = ("title", "subtitle", "eyebrow", "link_value")
    readonly_fields = ("slot",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
