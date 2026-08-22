from django.contrib import admin
from django.db import OperationalError, ProgrammingError

from apps.common.admin_utils import register_app_models
from .models import CheckoutSettings


@admin.register(CheckoutSettings)
class CheckoutSettingsAdmin(admin.ModelAdmin):
    list_display = ("existing_customer_otp_verification", "updated_at")
    fields = ("existing_customer_otp_verification",)

    def has_add_permission(self, request):
        try:
            return not CheckoutSettings.objects.exists()
        except (OperationalError, ProgrammingError):
            # Keep the admin index usable before a newly added migration is applied.
            return False

    def has_delete_permission(self, request, obj=None):
        return False


register_app_models("common", exclude={CheckoutSettings})
