from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import requests
from django.conf import settings


class PaymentGatewayError(Exception):
    """Raised when a gateway request cannot be completed or validated safely."""

    def __init__(self, message: str, *, code: str = "gateway_error", payload: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.payload = payload or {}


@dataclass(slots=True)
class InitiationResult:
    redirect_url: str
    gateway_reference: str = ""
    merchant_reference: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VerificationResult:
    status: str
    transaction_id: str = ""
    gateway_reference: str = ""
    amount: Decimal | None = None
    currency: str = "BDT"
    failure_code: str = ""
    failure_message: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class GatewayClient:
    provider = "base"

    def __init__(self, runtime_config=None):
        self.timeout = int(getattr(settings, "PAYMENT_GATEWAY_TIMEOUT", 20))
        self.session = requests.Session()
        self.runtime_config = runtime_config

    @property
    def environment(self) -> str:
        return getattr(self.runtime_config, "environment", "sandbox")

    @property
    def sandbox(self) -> bool:
        return self.environment == "sandbox"

    @property
    def values(self) -> dict[str, Any]:
        return dict(getattr(self.runtime_config, "values", {}) or {})

    def value(self, key: str, default: Any = "") -> Any:
        value = self.values.get(key, default)
        return default if value is None else value

    @staticmethod
    def money(value: Any) -> str:
        return f"{Decimal(str(value)):.2f}"

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        try:
            return self.session.request(method, url, **kwargs)
        except requests.RequestException as exc:
            raise PaymentGatewayError(
                f"{self.provider} is temporarily unreachable.",
                code="gateway_network_error",
                payload={"error": str(exc)},
            ) from exc

    def _json_response(self, response: requests.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise PaymentGatewayError(
                f"{self.provider} returned a non-JSON response.",
                code="invalid_gateway_response",
                payload={"http_status": response.status_code, "body": response.text[:500]},
            ) from exc
        if not response.ok:
            raise PaymentGatewayError(
                f"{self.provider} request failed with HTTP {response.status_code}.",
                code="gateway_http_error",
                payload={"http_status": response.status_code, "response": data},
            )
        return data if isinstance(data, dict) else {"data": data}

    def initiate(self, *, payment, callback_url: str) -> InitiationResult:  # pragma: no cover - interface
        raise NotImplementedError

    def verify(self, *, payment, callback_payload: dict[str, Any] | None = None) -> VerificationResult:  # pragma: no cover - interface
        raise NotImplementedError
