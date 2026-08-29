from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .crypto import CourierConfigEncryptionError
from .models import CourierConfig


PROVIDER_SCHEMAS: dict[str, dict[str, Any]] = {
    CourierConfig.Provider.PATHAO: {
        "label": "Pathao",
        "description": "Pathao Courier Merchant API: booking, live status sync and webhook-ready configuration.",
        "supports_sandbox": True,
        "supports_cancel": False,
        "sandbox_base_url": "https://courier-api-sandbox.pathao.com",
        "live_base_url": "https://api-hermes.pathao.com",
        "fields": [
            {"key": "client_id", "label": "Client ID", "required": True, "secret": False},
            {"key": "client_secret", "label": "Client Secret", "required": True, "secret": True},
            {"key": "username", "label": "Merchant Username / Email", "required": True, "secret": False},
            {"key": "password", "label": "Merchant Password", "required": True, "secret": True},
            {"key": "store_id", "label": "Pickup Store ID", "required": True, "secret": False},
            {"key": "webhook_secret", "label": "Webhook Integration Secret", "required": False, "secret": True},
            {"key": "default_weight_kg", "label": "Default Parcel Weight (kg)", "required": False, "secret": False, "default": "0.5"},
            {"key": "base_url", "label": "Custom Base URL", "required": False, "secret": False, "placeholder": "Leave blank for official environment URL"},
        ],
    },
    CourierConfig.Provider.STEADFAST: {
        "label": "Steadfast",
        "description": "Steadfast Courier API: order booking, delivery status sync, return request support and webhook verification.",
        "supports_sandbox": False,
        "supports_cancel": False,
        "live_base_url": "https://portal.steadfast.com.bd/api/v1",
        "fields": [
            {"key": "api_key", "label": "API Key", "required": True, "secret": True},
            {"key": "secret_key", "label": "Secret Key", "required": True, "secret": True},
            {"key": "webhook_bearer_token", "label": "Webhook Bearer Token", "required": False, "secret": True},
            {"key": "base_url", "label": "Custom Base URL", "required": False, "secret": False, "placeholder": "Leave blank for official API URL"},
        ],
    },
    CourierConfig.Provider.REDX: {
        "label": "RedX",
        "description": "RedX Merchant API: parcel booking, tracking, parcel details and provider-side cancellation where enabled.",
        "supports_sandbox": True,
        "supports_cancel": True,
        "sandbox_base_url": "https://sandbox.redx.com.bd/v1.0.0-beta",
        "live_base_url": "https://openapi.redx.com.bd/v1.0.0-beta",
        "fields": [
            {"key": "access_token", "label": "API Access Token", "required": True, "secret": True},
            {"key": "pickup_store_id", "label": "Pickup Store ID", "required": True, "secret": False},
            {"key": "webhook_token", "label": "Webhook Verification Token", "required": False, "secret": True},
            {"key": "default_weight_grams", "label": "Default Parcel Weight (grams)", "required": False, "secret": False, "default": "500"},
            {"key": "cancel_endpoint", "label": "Cancellation / Parcel Update Endpoint", "required": False, "secret": False, "placeholder": "Example: /parcels — only if confirmed by your RedX merchant contract"},
            {"key": "base_url", "label": "Custom Base URL", "required": False, "secret": False, "placeholder": "Leave blank for official environment URL"},
        ],
    },
    CourierConfig.Provider.CARRYBEE: {
        "label": "CarryBee",
        "description": "CarryBee Developers API v2: sandbox/live booking, address resolution, tracking, cancellation and webhook status updates.",
        "supports_sandbox": True,
        "supports_cancel": True,
        "sandbox_base_url": "https://stage-sandbox.carrybee.com",
        "live_base_url": "https://developers.carrybee.com",
        "fields": [
            {"key": "client_id", "label": "Client ID", "required": True, "secret": False},
            {"key": "client_secret", "label": "Client Secret", "required": True, "secret": True},
            {"key": "client_context", "label": "Client Context", "required": True, "secret": True},
            {"key": "store_id", "label": "Pickup Store ID", "required": True, "secret": False},
            {"key": "webhook_secret", "label": "Webhook Secret", "required": False, "secret": True},
            {"key": "default_delivery_type", "label": "Default Delivery Type (1 Normal, 2 Express)", "required": False, "secret": False, "default": "1"},
            {"key": "default_product_type", "label": "Default Product Type (1 Parcel, 2 Book, 3 Document)", "required": False, "secret": False, "default": "1"},
            {"key": "default_weight_grams", "label": "Default Parcel Weight (grams)", "required": False, "secret": False, "default": "500"},
            {"key": "base_url", "label": "Custom Base URL", "required": False, "secret": False, "placeholder": "Leave blank for official environment URL"},
        ],
    },
}

DEFAULT_COURIERS = (
    (CourierConfig.Provider.PATHAO, "Pathao", 10),
    (CourierConfig.Provider.STEADFAST, "Steadfast", 20),
    (CourierConfig.Provider.REDX, "RedX", 30),
    (CourierConfig.Provider.CARRYBEE, "CarryBee", 40),
)


@dataclass(slots=True)
class RuntimeCourierConfig:
    provider: str
    display_name: str
    active: bool
    environment: str
    values: dict[str, Any]

    @property
    def sandbox(self) -> bool:
        return self.environment == "sandbox"


def ensure_courier_configs() -> None:
    for provider, display_name, sort_order in DEFAULT_COURIERS:
        CourierConfig.objects.get_or_create(
            provider=provider,
            defaults={
                "display_name": display_name,
                "is_active": False,
                "sandbox_mode": provider != CourierConfig.Provider.STEADFAST,
                "sort_order": sort_order,
            },
        )


def schema_for(provider: str) -> dict[str, Any]:
    return PROVIDER_SCHEMAS.get(provider, {"label": provider, "description": "", "fields": [], "supports_sandbox": False, "supports_cancel": False})


def required_keys(provider: str) -> list[str]:
    return [f["key"] for f in schema_for(provider).get("fields", []) if f.get("required")]


def configuration_complete(provider: str, values: dict[str, Any]) -> bool:
    return all(str(values.get(k) or "").strip() for k in required_keys(provider))


def default_values(provider: str, environment: str) -> dict[str, Any]:
    schema = schema_for(provider)
    values: dict[str, Any] = {}
    for field in schema.get("fields", []):
        if field.get("default") not in (None, ""):
            values[field["key"]] = field["default"]
    base_key = "sandbox_base_url" if environment == "sandbox" else "live_base_url"
    values.setdefault("base_url", schema.get(base_key, ""))
    return values


def runtime_config(provider: str, *, require_active: bool = False, environment: str | None = None) -> RuntimeCourierConfig:
    ensure_courier_configs()
    cfg = CourierConfig.objects.filter(provider=provider).first()
    if cfg is None:
        raise ValueError(f"Unknown courier provider: {provider}")
    if require_active and not cfg.is_active:
        from .gateways.base import CourierGatewayError
        raise CourierGatewayError(f"{cfg.display_name} is currently disabled.", code="courier_inactive")

    schema = schema_for(provider)
    selected = environment or ("sandbox" if cfg.sandbox_mode and schema.get("supports_sandbox") else "live")
    if selected == "sandbox" and not schema.get("supports_sandbox"):
        selected = "live"
    try:
        stored = cfg.get_environment_config(selected)
    except CourierConfigEncryptionError as exc:
        from .gateways.base import CourierGatewayError
        raise CourierGatewayError(str(exc), code="courier_config_decryption_failed") from exc
    values = {**default_values(provider, selected), **stored}
    if not configuration_complete(provider, values):
        from .gateways.base import CourierGatewayError
        raise CourierGatewayError(f"{cfg.display_name} credentials are not configured for {selected}.", code="courier_not_configured")
    return RuntimeCourierConfig(provider=provider, display_name=cfg.display_name, active=cfg.is_active, environment=selected, values=values)


def is_provider_available(provider: str) -> bool:
    try:
        runtime_config(provider, require_active=True)
        return True
    except Exception:
        return False
