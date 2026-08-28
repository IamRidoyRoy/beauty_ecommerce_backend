from django.contrib import admin

from .models import TrackingEventLog, TrackingSettings


@admin.register(TrackingSettings)
class TrackingSettingsAdmin(admin.ModelAdmin):
    list_display = ("enabled", "browser_tracking_enabled", "server_tracking_enabled", "gtm_container_id", "meta_pixel_id", "updated_at")
    readonly_fields = ("meta_access_token_encrypted", "last_tested_at", "last_test_status", "last_test_message")

    def has_add_permission(self, request):
        return not TrackingSettings.objects.exists()


@admin.register(TrackingEventLog)
class TrackingEventLogAdmin(admin.ModelAdmin):
    list_display = ("event_name", "event_id", "status", "order_number", "http_status", "created_at")
    list_filter = ("event_name", "status")
    search_fields = ("event_id", "order_number", "error_message")
    readonly_fields = tuple(field.name for field in TrackingEventLog._meta.fields)
