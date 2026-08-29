from __future__ import annotations

from rest_framework import serializers

from .crypto import PaymentConfigEncryptionError
from .gateway_config import configuration_complete, default_values, schema_for
from .models import Payment, PaymentGatewayConfig, PaymentReconciliation


class PaymentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    customer_name = serializers.CharField(source="order.customer_name", read_only=True)
    customer_phone = serializers.CharField(source="order.customer_phone", read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id", "public_token", "order", "order_number", "customer_name", "customer_phone",
            "method", "currency", "transaction_id", "gateway_reference", "amount", "status",
            "initiated_at", "paid_at", "last_verified_at", "failure_code", "failure_message",
            "metadata", "created_at", "updated_at",
        )
        read_only_fields = fields


class PublicPaymentSerializer(serializers.ModelSerializer):
    payment_url = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            "public_token", "method", "currency", "amount", "status", "transaction_id",
            "gateway_reference", "initiated_at", "paid_at", "last_verified_at",
            "failure_code", "failure_message", "payment_url",
        )

    def get_payment_url(self, obj):
        return (obj.metadata or {}).get("redirect_url", "")


class PaymentReconciliationSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source="requested_by.full_name", read_only=True)

    class Meta:
        model = PaymentReconciliation
        fields = "__all__"


class PaymentGatewayConfigSerializer(serializers.ModelSerializer):
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
        model = PaymentGatewayConfig
        fields = (
            "id", "provider", "display_name", "is_active", "sandbox_mode", "sort_order",
            "sandbox_config", "live_config", "schema", "sandbox_values", "live_values",
            "sandbox_field_status", "live_field_status", "sandbox_configured", "live_configured",
            "current_environment", "current_environment_configured", "updated_by", "updated_by_name",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "provider", "schema", "sandbox_values", "live_values", "sandbox_field_status",
            "live_field_status", "sandbox_configured", "live_configured", "current_environment",
            "current_environment_configured", "updated_by", "updated_by_name", "created_at", "updated_at",
        )

    def get_schema(self, obj):
        return schema_for(obj.provider)

    def _values(self, obj, environment):
        try:
            stored = obj.get_environment_config(environment)
        except PaymentConfigEncryptionError:
            return {}
        values = {**default_values(obj.provider, environment), **stored}
        # Never return secret values. Non-secret values are useful for editing
        # and do not require an operator to re-enter merchant IDs or URLs.
        secret_keys = {field["key"] for field in schema_for(obj.provider).get("fields", []) if field.get("secret")}
        return {key: value for key, value in values.items() if key not in secret_keys}

    def get_sandbox_values(self, obj):
        return self._values(obj, "sandbox")

    def get_live_values(self, obj):
        return self._values(obj, "live")

    def _status(self, obj, environment):
        try:
            stored = obj.get_environment_config(environment)
        except PaymentConfigEncryptionError:
            stored = {}
        return {
            field["key"]: bool(str(stored.get(field["key"]) or "").strip())
            for field in schema_for(obj.provider).get("fields", [])
        }

    def get_sandbox_field_status(self, obj):
        return self._status(obj, "sandbox")

    def get_live_field_status(self, obj):
        return self._status(obj, "live")

    def _configured(self, obj, environment):
        try:
            values = {**default_values(obj.provider, environment), **obj.get_environment_config(environment)}
        except PaymentConfigEncryptionError:
            return False
        return configuration_complete(obj.provider, values)

    def get_sandbox_configured(self, obj):
        return self._configured(obj, "sandbox")

    def get_live_configured(self, obj):
        return self._configured(obj, "live")

    def get_current_environment(self, obj):
        return obj.environment

    def get_current_environment_configured(self, obj):
        return self._configured(obj, obj.environment)

    def _merge(self, obj, environment, incoming):
        try:
            current = obj.get_environment_config(environment)
        except PaymentConfigEncryptionError as exc:
            raise serializers.ValidationError({f"{environment}_config": str(exc)}) from exc
        fields = {field["key"]: field for field in schema_for(obj.provider).get("fields", [])}
        unknown = sorted(set(incoming) - set(fields))
        if unknown:
            raise serializers.ValidationError({f"{environment}_config": f"Unknown field(s): {', '.join(unknown)}"})
        merged = dict(current)
        for key, raw in incoming.items():
            field = fields[key]
            value = raw if isinstance(raw, str) else str(raw or "")
            # Blank secret means preserve the saved value. This prevents the UI
            # from needing to fetch or echo a stored credential back to browser.
            if field.get("secret") and not value.strip():
                continue
            merged[key] = value.strip() if key != "merchant_private_key" and key != "gateway_public_key" else value.strip()
        return merged

    def validate(self, attrs):
        obj = self.instance
        if obj is None:
            return attrs
        sandbox_values = self._merge(obj, "sandbox", attrs.get("sandbox_config", {}))
        live_values = self._merge(obj, "live", attrs.get("live_config", {}))
        sandbox_mode = attrs.get("sandbox_mode", obj.sandbox_mode)
        is_active = attrs.get("is_active", obj.is_active)
        selected = sandbox_values if sandbox_mode else live_values
        environment = "sandbox" if sandbox_mode else "live"
        if is_active and not configuration_complete(obj.provider, {**default_values(obj.provider, environment), **selected}):
            raise serializers.ValidationError({
                "is_active": f"Configure all required {environment} credentials before activating {obj.display_name}."
            })
        attrs["_sandbox_values"] = sandbox_values
        attrs["_live_values"] = live_values
        return attrs

    def update(self, instance, validated_data):
        sandbox_values = validated_data.pop("_sandbox_values", None)
        live_values = validated_data.pop("_live_values", None)
        validated_data.pop("sandbox_config", None)
        validated_data.pop("live_config", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if sandbox_values is not None:
            instance.set_environment_config("sandbox", sandbox_values)
        if live_values is not None:
            instance.set_environment_config("live", live_values)
        request = self.context.get("request")
        if request and getattr(request.user, "is_authenticated", False):
            instance.updated_by = request.user
        instance.save()
        return instance
