from rest_framework import serializers

from .models import City, DeliveryModule, Thana


class DeliveryModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryModule
        fields = ("id", "name", "code", "charge", "active", "sort_order")


class CitySerializer(serializers.ModelSerializer):
    delivery_module = DeliveryModuleSerializer(read_only=True)

    class Meta:
        model = City
        fields = ("id", "source_id", "name", "delivery_module", "active")


class ThanaSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source="city.name", read_only=True)
    effective_delivery_module = serializers.SerializerMethodField()

    class Meta:
        model = Thana
        fields = (
            "id",
            "source_id",
            "city",
            "city_name",
            "name",
            "delivery_module",
            "effective_delivery_module",
            "active",
        )

    def get_effective_delivery_module(self, obj):
        module = obj.delivery_module or obj.city.delivery_module
        return DeliveryModuleSerializer(module).data


class AdminCitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = "__all__"


class AdminThanaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Thana
        fields = "__all__"
