from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings

from .crypto import PaymentConfigEncryptionError
from .models import Payment, PaymentGatewayConfig


PROVIDER_SCHEMAS: dict[str, dict[str, Any]] = {
    PaymentGatewayConfig.Provider.SSLCOMMERZ: {
        "label": "SSLCOMMERZ",
        "description": "Cards, mobile banking and bank channels through SSLCOMMERZ hosted checkout.",
        "sandbox_base_url": "https://sandbox.sslcommerz.com",
        "live_base_url": "https://securepay.sslcommerz.com",
        "fields": [
            {"key": "store_id", "label": "Store ID", "required": True, "secret": False},
            {"key": "store_password", "label": "Store Password", "required": True, "secret": True},
            {"key": "base_url", "label": "Custom Base URL", "required": False, "secret": False, "placeholder": "Leave blank to use the official environment URL"},
        ],
    },
    PaymentGatewayConfig.Provider.BKASH: {
        "label": "bKash",
        "description": "bKash Tokenized Checkout integration.",
        "sandbox_base_url": "https://tokenized.sandbox.bka.sh/v1.2.0-beta",
        "live_base_url": "https://tokenized.pay.bka.sh/v1.2.0-beta",
        "fields": [
            {"key": "app_key", "label": "App Key", "required": True, "secret": True},
            {"key": "app_secret", "label": "App Secret", "required": True, "secret": True},
            {"key": "username", "label": "Username", "required": True, "secret": True},
            {"key": "password", "label": "Password", "required": True, "secret": True},
            {"key": "base_url", "label": "Custom Base URL", "required": False, "secret": False, "placeholder": "Leave blank to use the official environment URL"},
        ],
    },
    PaymentGatewayConfig.Provider.NAGAD: {
        "label": "Nagad",
        "description": "Nagad Remote Payment Gateway integration.",
        "sandbox_base_url": "https://sandboxapi.nagad.com.bd/remote-payment-gateway-1.0/api/dfs",
        "live_base_url": "https://api.nagad.com.bd/remote-payment-gateway-1.0/api/dfs",
        "fields": [
            {"key": "merchant_id", "label": "Merchant ID", "required": True, "secret": False},
            {"key": "merchant_number", "label": "Merchant Number", "required": False, "secret": False},
            {"key": "merchant_private_key", "label": "Merchant Private Key", "required": True, "secret": True, "multiline": True},
            {"key": "gateway_public_key", "label": "Gateway Public Key", "required": True, "secret": True, "multiline": True},
            {"key": "client_ip", "label": "Client IPv4", "required": False, "secret": False, "placeholder": "Public server IP; defaults to 127.0.0.1 in development"},
            {"key": "api_version", "label": "API Version", "required": False, "secret": False, "default": "v-0.2.0"},
            {"key": "client_type", "label": "Client Type", "required": False, "secret": False, "default": "PC_WEB"},
            {"key": "currency_code", "label": "Currency Code", "required": False, "secret": False, "default": "050"},
            {"key": "base_url", "label": "Custom Base URL", "required": False, "secret": False, "placeholder": "Leave blank to use the official environment URL"},
        ],
    },
}


DEFAULT_GATEWAYS = (
    (PaymentGatewayConfig.Provider.SSLCOMMERZ, "SSLCOMMERZ", 10),
    (PaymentGatewayConfig.Provider.BKASH, "bKash", 20),
    (PaymentGatewayConfig.Provider.NAGAD, "Nagad", 30),
)


@dataclass(slots=True)
class RuntimeGatewayConfig:
    provider: str
    display_name: str
    active: bool
    environment: str
    values: dict[str, Any]

    @property
    def sandbox(self) -> bool:
        return self.environment == "sandbox"


def ensure_gateway_configs() -> None:
    for provider, display_name, sort_order in DEFAULT_GATEWAYS:
        PaymentGatewayConfig.objects.get_or_create(
            provider=provider,
            defaults={
                "display_name": display_name,
                "is_active": False,
                "sandbox_mode": True,
                "sort_order": sort_order,
            },
        )


def schema_for(provider: str) -> dict[str, Any]:
    return PROVIDER_SCHEMAS.get(provider, {"label": provider, "description": "", "fields": []})


def required_keys(provider: str) -> list[str]:
    return [field["key"] for field in schema_for(provider).get("fields", []) if field.get("required")]


def configuration_complete(provider: str, values: dict[str, Any]) -> bool:
    return all(str(values.get(key) or "").strip() for key in required_keys(provider))


def default_values(provider: str, environment: str) -> dict[str, Any]:
    schema = schema_for(provider)
    values: dict[str, Any] = {}
    for field in schema.get("fields", []):
        if field.get("default") not in (None, ""):
            values[field["key"]] = field["default"]
    base_key = "sandbox_base_url" if environment == "sandbox" else "live_base_url"
    values.setdefault("base_url", schema.get(base_key, ""))
    return values


def _legacy_values(provider: str, environment: str) -> dict[str, Any]:
    """Fallback only for already-created payments while migrating from .env.

    New checkout availability is controlled by the database config, not this
    fallback. The old env values are used only when an existing payment needs
    verification and no database credentials have been saved yet.
    """
    sandbox = environment == "sandbox"
    if provider == PaymentGatewayConfig.Provider.SSLCOMMERZ:
        if bool(getattr(settings, "SSLCOMMERZ_SANDBOX", True)) != sandbox:
            return {}
        return {
            "store_id": getattr(settings, "SSLCOMMERZ_STORE_ID", ""),
            "store_password": getattr(settings, "SSLCOMMERZ_STORE_PASSWORD", ""),
            "base_url": "",
        }
    if provider == PaymentGatewayConfig.Provider.BKASH:
        if bool(getattr(settings, "BKASH_SANDBOX", True)) != sandbox:
            return {}
        return {
            "app_key": getattr(settings, "BKASH_APP_KEY", ""),
            "app_secret": getattr(settings, "BKASH_APP_SECRET", ""),
            "username": getattr(settings, "BKASH_USERNAME", ""),
            "password": getattr(settings, "BKASH_PASSWORD", ""),
            "base_url": getattr(settings, "BKASH_BASE_URL", ""),
        }
    if provider == PaymentGatewayConfig.Provider.NAGAD:
        if bool(getattr(settings, "NAGAD_SANDBOX", True)) != sandbox:
            return {}
        return {
            "merchant_id": getattr(settings, "NAGAD_MERCHANT_ID", ""),
            "merchant_number": getattr(settings, "NAGAD_MERCHANT_NUMBER", ""),
            "merchant_private_key": getattr(settings, "NAGAD_MERCHANT_PRIVATE_KEY", ""),
            "gateway_public_key": getattr(settings, "NAGAD_GATEWAY_PUBLIC_KEY", ""),
            "client_ip": getattr(settings, "NAGAD_CLIENT_IP", ""),
            "api_version": getattr(settings, "NAGAD_API_VERSION", "v-0.2.0"),
            "client_type": getattr(settings, "NAGAD_CLIENT_TYPE", "PC_WEB"),
            "currency_code": getattr(settings, "NAGAD_CURRENCY_CODE", "050"),
            "base_url": getattr(settings, "NAGAD_BASE_URL", ""),
        }
    return {}


def runtime_config(
    provider: str,
    *,
    require_active: bool = False,
    environment: str | None = None,
    allow_legacy_fallback: bool = False,
) -> RuntimeGatewayConfig:
    ensure_gateway_configs()
    config = PaymentGatewayConfig.objects.filter(provider=provider).first()
    if config is None:
        raise ValueError(f"Unknown payment gateway: {provider}")
    if require_active and not config.is_active:
        from .gateways.base import PaymentGatewayError
        raise PaymentGatewayError(f"{config.display_name} is currently disabled.", code="gateway_inactive")

    selected_environment = environment or ("sandbox" if config.sandbox_mode else "live")
    try:
        stored = config.get_environment_config(selected_environment)
    except PaymentConfigEncryptionError as exc:
        from .gateways.base import PaymentGatewayError
        raise PaymentGatewayError(str(exc), code="gateway_config_decryption_failed") from exc

    values = {**default_values(provider, selected_environment), **stored}
    if not configuration_complete(provider, values) and allow_legacy_fallback:
        legacy = _legacy_values(provider, selected_environment)
        values = {**default_values(provider, selected_environment), **legacy, **stored}

    if not configuration_complete(provider, values):
        from .gateways.base import PaymentGatewayError
        raise PaymentGatewayError(f"{config.display_name} credentials are not configured for {selected_environment}.", code="gateway_not_configured")

    return RuntimeGatewayConfig(
        provider=provider,
        display_name=config.display_name,
        active=config.is_active,
        environment=selected_environment,
        values=values,
    )


def is_provider_available(provider: str) -> bool:
    try:
        runtime_config(provider, require_active=True)
        return True
    except Exception:
        return False


def is_payment_method_available(method: str) -> bool:
    if method == Payment.Method.COD:
        return True
    provider = {
        Payment.Method.SSLCOMMERZ: PaymentGatewayConfig.Provider.SSLCOMMERZ,
        Payment.Method.CARD: PaymentGatewayConfig.Provider.SSLCOMMERZ,
        Payment.Method.BKASH: PaymentGatewayConfig.Provider.BKASH,
        Payment.Method.NAGAD: PaymentGatewayConfig.Provider.NAGAD,
    }.get(method)
    return bool(provider and is_provider_available(provider))
