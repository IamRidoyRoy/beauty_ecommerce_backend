import re
from rest_framework import serializers
from .models import SiteBrandingSettings

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class SiteBrandingSettingsSerializer(serializers.ModelSerializer):
    clear_website_logo = serializers.BooleanField(write_only=True, required=False, default=False)
    clear_dashboard_logo = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = SiteBrandingSettings
        fields = (
            "id",
            "website_brand_mode", "website_name", "website_tagline", "website_logo",
            "dashboard_brand_mode", "dashboard_name", "dashboard_tagline", "dashboard_logo",
            "primary_color", "secondary_color",
            "clear_website_logo", "clear_dashboard_logo",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        extra_kwargs = {
            "website_logo": {"required": False, "allow_null": True},
            "dashboard_logo": {"required": False, "allow_null": True},
        }

    def _validate_hex(self, value):
        value = str(value or "").strip()
        if not HEX_RE.fullmatch(value):
            raise serializers.ValidationError("Use a 6-digit HEX color, for example #d43a89.")
        return value.lower()

    def validate_primary_color(self, value):
        return self._validate_hex(value)

    def validate_secondary_color(self, value):
        return self._validate_hex(value)

    def _validate_logo(self, file):
        if file and file.size > 3 * 1024 * 1024:
            raise serializers.ValidationError("Logo must be 3 MB or smaller.")
        return file

    def validate_website_logo(self, value):
        return self._validate_logo(value)

    def validate_dashboard_logo(self, value):
        return self._validate_logo(value)

    def validate(self, attrs):
        website_mode = attrs.get("website_brand_mode", getattr(self.instance, "website_brand_mode", "text"))
        dashboard_mode = attrs.get("dashboard_brand_mode", getattr(self.instance, "dashboard_brand_mode", "text"))
        website_name = attrs.get("website_name", getattr(self.instance, "website_name", ""))
        dashboard_name = attrs.get("dashboard_name", getattr(self.instance, "dashboard_name", ""))
        if website_mode == "text" and not str(website_name).strip():
            raise serializers.ValidationError({"website_name": "Website name is required when text mode is selected."})
        if dashboard_mode == "text" and not str(dashboard_name).strip():
            raise serializers.ValidationError({"dashboard_name": "Dashboard name is required when text mode is selected."})
        return attrs

    def update(self, instance, validated_data):
        clear_website = validated_data.pop("clear_website_logo", False)
        clear_dashboard = validated_data.pop("clear_dashboard_logo", False)
        if clear_website and instance.website_logo:
            instance.website_logo.delete(save=False)
            instance.website_logo = None
        if clear_dashboard and instance.dashboard_logo:
            instance.dashboard_logo.delete(save=False)
            instance.dashboard_logo = None
        return super().update(instance, validated_data)
