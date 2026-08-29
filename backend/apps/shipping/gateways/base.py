from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import requests
from django.conf import settings


class CourierGatewayError(RuntimeError):
    def __init__(self, message: str, *, code: str = "courier_error", response: Any = None):
        super().__init__(message)
        self.code = code
        self.response = response


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
        return data

    @abstractmethod
    def test_connection(self) -> dict[str, Any]: ...

    @abstractmethod
    def create_shipment(self, order, *, options: dict[str, Any] | None = None) -> CourierResult: ...

    @abstractmethod
    def track(self, shipment) -> CourierResult: ...

    def cancel_shipment(self, shipment, *, reason: str = "") -> CourierResult:
        raise CourierGatewayError(f"{self.runtime.display_name} does not expose a verified API cancellation endpoint.", code="cancel_not_supported")
