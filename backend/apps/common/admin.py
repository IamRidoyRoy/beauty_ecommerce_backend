from django.contrib import admin

from apps.common.admin_utils import register_app_models
from .models import CheckoutSettings


@admin.register(CheckoutSettings)
class CheckoutSettingsAdmin(admin.ModelAdmin):
    list_display = ("existing_customer_otp_verification", "updated_at")
    fields = ("existing_customer_otp_verification",)

    def has_add_permission(self, request):
        return not CheckoutSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


register_app_models("common", exclude={CheckoutSettings})
