from __future__ import annotations

from rest_framework import serializers

from .courier_config import configuration_complete, default_values, schema_for
from .crypto import CourierConfigEncryptionError
from .models import CourierConfig, CourierEvent, Shipment, ShippingMethod


class ShippingMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingMethod
        fields = ("id", "name", "code", "base_charge", "estimated_days", "free_threshold", "active")


class ShipmentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    customer_name = serializers.CharField(source="order.customer_name", read_only=True)
    customer_phone = serializers.CharField(source="order.customer_phone", read_only=True)
    courier_display = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = Shipment
        fields = (
            "id", "order", "order_number", "customer_name", "customer_phone", "courier", "courier_display", "environment",
            "external_id", "tracking_code", "status", "provider_status", "provider_message", "booking_source", "booked_by",
            "payload", "last_synced_at", "booked_at", "picked_up_at", "dispatched_at", "delivered_at", "cancelled_at",
            "can_cancel", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_courier_display(self, obj):
        return schema_for((obj.courier or "").lower()).get("label", obj.courier or "Other")

    def get_can_cancel(self, obj):
        provider = (obj.courier or "").lower()
        cache = self.context.setdefault("_courier_cancel_capability", {})
        if provider not in cache:
            cfg = CourierConfig.objects.filter(provider=provider).only("cancel_api_enabled").first()
            cache[provider] = bool(schema_for(provider).get("supports_cancel")) and bool(cfg and cfg.cancel_api_enabled)
        return cache[provider] and obj.status not in {"delivered", "cancelled", "returned"}


class CourierEventSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source="requested_by.full_name", read_only=True)
    class Meta:
        model = CourierEvent
        fields = "__all__"


class CourierConfigSerializer(serializers.ModelSerializer):
    sandbox_config = serializers.DictField(write_only=True, required=False)
    live_config = serializers.DictField(write_only=True, required=False)
    schema = serializers.SerializerMethodField()
    sandbox_values = serializers.SerializerMethodField()
    live_values = serializers.SerializerMethodField()
    sandbox_field_status = serializers.SerializerMethodField()
    live_field_status = serializers.SerializerMethodField()
    sandbox_configured = serializers.SerializerMethodField()
    live_configured = serializers.SerializerMethodField()
    current_environment = serializers.SerializerMethodField()
    current_environment_configured = serializers.SerializerMethodField()
    updated_by_name = serializers.CharField(source="updated_by.full_name", read_only=True)

    class Meta:
        model = CourierConfig
        fields = (
            "id", "provider", "display_name", "is_active", "sandbox_mode", "sort_order", "auto_book_enabled", "auto_book_order_status", "cancel_api_enabled",
            "sandbox_config", "live_config", "schema", "sandbox_values", "live_values", "sandbox_field_status", "live_field_status",
            "sandbox_configured", "live_configured", "current_environment", "current_environment_configured", "updated_by", "updated_by_name",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "provider", "schema", "sandbox_values", "live_values", "sandbox_field_status", "live_field_status", "sandbox_configured",
            "live_configured", "current_environment", "current_environment_configured", "updated_by", "updated_by_name", "created_at", "updated_at",
        )

    def get_schema(self, obj):
        return schema_for(obj.provider)

    def _stored(self, obj, environment):
        try:
            return obj.get_environment_config(environment)
        except CourierConfigEncryptionError:
            return {}

    def _values(self, obj, environment):
        stored = self._stored(obj, environment)
        values = {**default_values(obj.provider, environment), **stored}
        secret_keys = {f["key"] for f in schema_for(obj.provider).get("fields", []) if f.get("secret")}
        return {k: v for k, v in values.items() if k not in secret_keys}

    def _status(self, obj, environment):
        stored = self._stored(obj, environment)
        return {f["key"]: bool(str(stored.get(f["key"]) or "").strip()) for f in schema_for(obj.provider).get("fields", []) if f.get("secret")}

    def get_sandbox_values(self, obj): return self._values(obj, "sandbox")
    def get_live_values(self, obj): return self._values(obj, "live")
    def get_sandbox_field_status(self, obj): return self._status(obj, "sandbox")
    def get_live_field_status(self, obj): return self._status(obj, "live")

    def get_sandbox_configured(self, obj):
        values = {**default_values(obj.provider, "sandbox"), **self._stored(obj, "sandbox")}
        return bool(schema_for(obj.provider).get("supports_sandbox")) and configuration_complete(obj.provider, values)

    def get_live_configured(self, obj):
        values = {**default_values(obj.provider, "live"), **self._stored(obj, "live")}
        return configuration_complete(obj.provider, values)

    def get_current_environment(self, obj):
        return "sandbox" if obj.sandbox_mode and schema_for(obj.provider).get("supports_sandbox") else "live"

    def get_current_environment_configured(self, obj):
        return self.get_sandbox_configured(obj) if self.get_current_environment(obj) == "sandbox" else self.get_live_configured(obj)

    def validate(self, attrs):
        provider = self.instance.provider if self.instance else attrs.get("provider")
        schema = schema_for(provider)
        sandbox_mode = attrs.get("sandbox_mode", getattr(self.instance, "sandbox_mode", True))
        if sandbox_mode and not schema.get("supports_sandbox"):
            raise serializers.ValidationError({"sandbox_mode": f"{schema.get('label', provider)} does not provide a documented public sandbox environment."})
        return attrs

    def _merge_environment(self, instance, environment, incoming):
        if incoming is None:
            return
        current = self._stored(instance, environment)
        fields = schema_for(instance.provider).get("fields", [])
        secret_keys = {f["key"] for f in fields if f.get("secret")}
        for key, value in incoming.items():
            if key in secret_keys and (value is None or str(value).strip() == ""):
                continue
            current[key] = value
        instance.set_environment_config(environment, current)

    def update(self, instance, validated_data):
        sandbox = validated_data.pop("sandbox_config", None)
        live = validated_data.pop("live_config", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        self._merge_environment(instance, "sandbox", sandbox)
        self._merge_environment(instance, "live", live)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            instance.updated_by = request.user
        selected = "sandbox" if instance.sandbox_mode and schema_for(instance.provider).get("supports_sandbox") else "live"
        if instance.is_active:
            values = {**default_values(instance.provider, selected), **self._stored(instance, selected)}
            if not configuration_complete(instance.provider, values):
                raise serializers.ValidationError({"is_active": f"Complete {selected} credentials before activating {instance.display_name}."})
        instance.save()
        return instance
