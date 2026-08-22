from django.contrib import admin

from .models import City, DeliveryModule, Thana


@admin.register(DeliveryModule)
class DeliveryModuleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code", "charge", "active", "sort_order")
    list_editable = ("charge", "active", "sort_order")
    search_fields = ("name", "code")


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("id", "source_id", "name", "delivery_module", "active")
    list_filter = ("delivery_module", "active")
    list_editable = ("delivery_module", "active")
    search_fields = ("name",)
    list_select_related = ("delivery_module",)
    list_per_page = 100


@admin.register(Thana)
class ThanaAdmin(admin.ModelAdmin):
    list_display = ("id", "source_id", "name", "city", "effective_module", "active")
    list_filter = ("city", "delivery_module", "active")
    search_fields = ("name", "city__name")
    raw_id_fields = ("city",)
    list_select_related = ("city__delivery_module", "delivery_module")
    list_per_page = 100

    @admin.display(description="Delivery module")
    def effective_module(self, obj):
        return obj.delivery_module or obj.city.delivery_module
