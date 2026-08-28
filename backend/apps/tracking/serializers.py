import re

from rest_framework import serializers

from .crypto import encrypt_secret
from .models import DEFAULT_TRACKING_EVENTS, TrackingEventLog, TrackingSettings
from .services import STANDARD_EVENTS, normalize_event_name


class TrackingPublicConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingSettings
        fields = (
            "enabled",
            "browser_tracking_enabled",
            "server_tracking_enabled",
            "require_marketing_consent",
            "gtm_container_id",
            "meta_pixel_id",
            "currency",
            "enabled_events",
        )


class TrackingSettingsAdminSerializer(serializers.ModelSerializer):
    meta_access_token = serializers.CharField(write_only=True, required=False, allow_blank=True, trim_whitespace=False)
    has_access_token = serializers.SerializerMethodField()
    masked_access_token = serializers.SerializerMethodField()

    class Meta:
        model = TrackingSettings
        fields = (
            "id",
            "enabled",
            "browser_tracking_enabled",
            "server_tracking_enabled",
            "require_marketing_consent",
            "gtm_container_id",
            "meta_pixel_id",
            "meta_api_version",
            "meta_access_token",
            "has_access_token",
            "masked_access_token",
            "meta_test_event_code",
            "currency",
            "enabled_events",
            "last_tested_at",
            "last_test_status",
            "last_test_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "has_access_token",
            "masked_access_token",
            "last_tested_at",
            "last_test_status",
            "last_test_message",
            "created_at",
            "updated_at",
        )

    def get_has_access_token(self, obj):
        return bool(obj.meta_access_token_encrypted)

    def get_masked_access_token(self, obj):
        return "••••••••••••" if obj.meta_access_token_encrypted else ""

    def validate_gtm_container_id(self, value):
        value = value.strip().upper()
        if value and not re.fullmatch(r"GTM-[A-Z0-9]+", value):
            raise serializers.ValidationError("Use a valid Google Tag Manager web container ID such as GTM-ABC1234.")
        return value

    def validate_meta_pixel_id(self, value):
        value = value.strip()
        if value and not value.isdigit():
            raise serializers.ValidationError("Meta Pixel ID must contain digits only.")
        return value

    def validate_meta_api_version(self, value):
        value = value.strip().lower()
        if value and not re.fullmatch(r"v\d+\.\d+", value):
            raise serializers.ValidationError("Use a Graph API version such as v26.0.")
        return value or "v26.0"

    def validate_enabled_events(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Enabled events must be an object of event-name booleans.")
        cleaned = dict(DEFAULT_TRACKING_EVENTS)
        for key, enabled in value.items():
            event = normalize_event_name(str(key))
            if event in STANDARD_EVENTS:
                cleaned[event] = bool(enabled)
        return cleaned

    def update(self, instance, validated_data):
        token = validated_data.pop("meta_access_token", None)
        instance = super().update(instance, validated_data)
        if token is not None and token.strip():
            instance.meta_access_token_encrypted = encrypt_secret(token)
            instance.save(update_fields=["meta_access_token_encrypted", "updated_at"])
        return instance


class TrackingEventIngestSerializer(serializers.Serializer):
    event_name = serializers.CharField(required=False, allow_blank=True)
    event_type = serializers.CharField(required=False, allow_blank=True)
    event_id = serializers.CharField(required=False, allow_blank=True, max_length=160)
    event_source_url = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    product_id_ref = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    variant_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    quantity = serializers.IntegerField(required=False, default=1, min_value=1)
    custom_data = serializers.JSONField(required=False, default=dict)
    metadata = serializers.JSONField(required=False, default=dict)
    fbp = serializers.CharField(required=False, allow_blank=True, max_length=255)
    fbc = serializers.CharField(required=False, allow_blank=True, max_length=255)
    consent = serializers.BooleanField(required=False, default=True)
    session_token = serializers.CharField(required=False, allow_blank=True, max_length=128)
    cart_token = serializers.CharField(required=False, allow_blank=True, max_length=128)

    def validate(self, attrs):
        name = attrs.get("event_name") or attrs.get("event_type")
        name = normalize_event_name(name or "")
        if name not in STANDARD_EVENTS:
            raise serializers.ValidationError({"event_name": f"Unsupported event. Use one of: {', '.join(sorted(STANDARD_EVENTS))}."})
        attrs["event_name"] = name
        return attrs


class TrackingEventLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingEventLog
        fields = (
            "id",
            "event_name",
            "event_id",
            "source",
            "status",
            "order_number",
            "http_status",
            "custom_data",
            "response_data",
            "error_message",
            "created_at",
        )
