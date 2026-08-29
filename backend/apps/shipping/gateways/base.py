from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import requests
from django.conf import settings


def provider_error_details(data: Any) -> list[str]:
    """Return safe field-level validation messages from courier API responses."""
    if not isinstance(data, dict):
        return []
    raw = data.get("errors") or data.get("validation") or data.get("error")
    if not raw:
        return []
    details: list[str] = []

    def add(prefix: str, value: Any) -> None:
        if value in (None, ""):
            return
        if isinstance(value, dict):
            for key, child in value.items():
                add(f"{prefix}.{key}" if prefix else str(key), child)
            return
        if isinstance(value, (list, tuple)):
            for child in value:
                add(prefix, child)
            return
        text = str(value).strip()
        if text:
            details.append(f"{prefix}: {text}" if prefix else text)

    add("", raw)
    # Keep API responses readable in the dashboard and avoid pathological payloads.
    return details[:12]


class CourierGatewayError(RuntimeError):
    def __init__(self, message: str, *, code: str = "courier_error", response: Any = None):
        details = provider_error_details(response)
        if details and not any(detail in message for detail in details):
            message = f"{message} " + " | ".join(details)
        super().__init__(message)
        self.code = code
        self.response = response
        self.details = details


@dataclass(slots=True)
class CourierResult:
    external_id: str = ""
    tracking_code: str = ""
    provider_status: str = ""
    status: str = "pending"
    message: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class BaseCourierAdapter(ABC):
    provider = ""
    supports_cancel = False

    def __init__(self, runtime):
        self.runtime = runtime
        self.values = runtime.values
        self.base_url = str(self.values.get("base_url") or "").rstrip("/")
        self.timeout = int(getattr(settings, "COURIER_API_TIMEOUT", 20))

    def _request(self, method: str, url: str, **kwargs):
        try:
            response = requests.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise CourierGatewayError(f"Unable to reach {self.runtime.display_name}: {exc}", code="courier_network_error") from exc
        try:
            data = response.json()
        except ValueError:
            data = {"raw": response.text[:2000]}
        if response.status_code >= 400:
            message = data.get("message") if isinstance(data, dict) else None
            raise CourierGatewayError(message or f"{self.runtime.display_name} returned HTTP {response.status_code}.", code="courier_http_error", response=data)
        # A few courier APIs occasionally return an HTTP 200 envelope whose own
        # code/type still represents a validation failure. Treat it as an error.
        if isinstance(data, dict):
            api_type = str(data.get("type") or "").lower()
            try:
                api_code = int(data.get("code") or 0)
            except (TypeError, ValueError):
                api_code = 0
            if api_type == "error" or api_code >= 400:
                raise CourierGatewayError(str(data.get("message") or f"{self.runtime.display_name} rejected the request."), code="courier_api_error", response=data)
        return data

    @abstractmethod
    def test_connection(self) -> dict[str, Any]: ...

    @abstractmethod
    def create_shipment(self, order, *, options: dict[str, Any] | None = None) -> CourierResult: ...

    @abstractmethod
    def track(self, shipment) -> CourierResult: ...

    def cancel_shipment(self, shipment, *, reason: str = "") -> CourierResult:
        raise CourierGatewayError(f"{self.runtime.display_name} does not expose a verified API cancellation endpoint.", code="cancel_not_supported")
