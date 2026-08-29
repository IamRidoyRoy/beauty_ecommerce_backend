from __future__ import annotations

from decimal import Decimal
from typing import Any

from .base import BaseCourierAdapter, CourierGatewayError, CourierResult


def _num(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class PathaoAdapter(BaseCourierAdapter):
    provider = "pathao"
    supports_cancel = False

    def __init__(self, runtime):
        super().__init__(runtime)
        self._token = ""

    def _access_token(self) -> str:
        if self._token:
            return self._token
        payload = {
            "client_id": self.values["client_id"],
            "client_secret": self.values["client_secret"],
            "grant_type": "password",
            "username": self.values["username"],
            "password": self.values["password"],
        }
        data = self._request("POST", f"{self.base_url}/aladdin/api/v1/issue-token", json=payload, headers={"Accept": "application/json", "Content-Type": "application/json"})
        token = data.get("access_token") or (data.get("data") or {}).get("access_token")
        if not token:
            raise CourierGatewayError("Pathao did not return an access token.", code="pathao_auth_failed", response=data)
        self._token = token
        return token

    def _headers(self):
        return {"Authorization": f"Bearer {self._access_token()}", "Accept": "application/json", "Content-Type": "application/json"}

    def test_connection(self) -> dict[str, Any]:
        return self._request("GET", f"{self.base_url}/aladdin/api/v1/stores", headers=self._headers())

    def create_shipment(self, order, *, options=None) -> CourierResult:
        options = options or {}
        address = order.shipping_address_snapshot or {}
        qty = sum(int(x.quantity) for x in order.items.all())
        descriptions = ", ".join(x.product_name_snapshot for x in order.items.all())[:250]
        weight = _num(options.get("weight_kg") or self.values.get("default_weight_kg"), 0.5)
        latest_payment = order.payments.order_by("-created_at").first()
        cod_amount = order.total if latest_payment and latest_payment.method == "cod" and order.payment_status != "paid" else Decimal("0")
        payload = {
            "store_id": int(options.get("store_id") or self.values["store_id"]),
            "merchant_order_id": order.order_number,
            "recipient_name": order.customer_name[:100],
            "recipient_phone": order.customer_phone,
            "recipient_address": str(address.get("address") or address.get("full_address") or address.get("street") or "")[:250],
            "delivery_type": int(options.get("delivery_type") or 48),
            "item_type": int(options.get("item_type") or 2),
            "special_instruction": str(options.get("instruction") or order.notes or "")[:250],
            "item_quantity": max(qty, 1),
            "item_weight": max(weight, 0.5),
            "amount_to_collect": float(cod_amount),
            "item_description": descriptions,
        }
        if not payload["recipient_address"]:
            raise CourierGatewayError("Order shipping address is missing.", code="invalid_shipping_address")
        data = self._request("POST", f"{self.base_url}/aladdin/api/v1/orders", json=payload, headers=self._headers())
        body = data.get("data") or data
        consignment = str(body.get("consignment_id") or body.get("id") or "")
        if not consignment:
            raise CourierGatewayError("Pathao booking response did not include a consignment ID.", code="pathao_booking_invalid", response=data)
        provider_status = str(body.get("order_status") or body.get("status") or "booked")
        return CourierResult(external_id=consignment, tracking_code=consignment, provider_status=provider_status, status="booked", message=str(data.get("message") or "Booked with Pathao"), raw={"request": payload, "response": data})

    @staticmethod
    def _map_status(value: str) -> str:
        s = (value or "").lower().replace("-", "_").replace(" ", "_")
        if "return" in s:
            return "returned"
        if "cancel" in s:
            return "cancelled"
        if "fail" in s:
            return "failed"
        if s in {"out_for_delivery", "delivery_in_progress", "on_the_way_to_delivery"} or "out_for_delivery" in s:
            return "out_for_delivery"
        if s in {"delivered", "delivery_completed", "completed"} or s.endswith("_delivered"):
            return "delivered"
        if "transit" in s or "hub" in s or "sorting" in s:
            return "in_transit"
        if "pick" in s:
            return "picked"
        if "book" in s or "pending" in s or "request" in s or "review" in s:
            return "booked"
        return "in_transit" if s else "booked"

    def track(self, shipment) -> CourierResult:
        cid = shipment.external_id or shipment.tracking_code
        if not cid:
            raise CourierGatewayError("Shipment has no Pathao consignment ID.", code="tracking_id_missing")
        data = self._request("GET", f"{self.base_url}/aladdin/api/v1/orders/{cid}/info", headers=self._headers())
        body = data.get("data") or data
        provider_status = str(body.get("order_status") or body.get("status") or "")
        return CourierResult(external_id=str(cid), tracking_code=str(cid), provider_status=provider_status, status=self._map_status(provider_status), message=str(data.get("message") or provider_status), raw=data)
