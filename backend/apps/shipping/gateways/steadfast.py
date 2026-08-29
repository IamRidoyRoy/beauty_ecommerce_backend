from __future__ import annotations

from decimal import Decimal
from typing import Any

from .base import BaseCourierAdapter, CourierGatewayError, CourierResult


class SteadfastAdapter(BaseCourierAdapter):
    provider = "steadfast"
    supports_cancel = False

    def _headers(self):
        return {"Api-Key": self.values["api_key"], "Secret-Key": self.values["secret_key"], "Content-Type": "application/json", "Accept": "application/json"}

    def test_connection(self) -> dict[str, Any]:
        return self._request("GET", f"{self.base_url}/get_balance", headers=self._headers())

    def create_shipment(self, order, *, options=None) -> CourierResult:
        options = options or {}
        address = order.shipping_address_snapshot or {}
        latest_payment = order.payments.order_by("-created_at").first()
        cod_amount = order.total if latest_payment and latest_payment.method == "cod" and order.payment_status != "paid" else Decimal("0")
        payload = {
            "invoice": order.order_number,
            "recipient_name": order.customer_name[:100],
            "recipient_phone": order.customer_phone,
            "recipient_address": str(address.get("address") or address.get("full_address") or address.get("street") or "")[:250],
            "cod_amount": float(cod_amount),
            "note": str(options.get("instruction") or order.notes or "")[:250],
            "item_description": ", ".join(x.product_name_snapshot for x in order.items.all())[:250],
            "total_lot": max(sum(int(x.quantity) for x in order.items.all()), 1),
            "delivery_type": int(options.get("delivery_type") or 0),
        }
        if not payload["recipient_address"]:
            raise CourierGatewayError("Order shipping address is missing.", code="invalid_shipping_address")
        data = self._request("POST", f"{self.base_url}/create_order", json=payload, headers=self._headers())
        body = data.get("consignment") or data.get("data") or data
        cid = str(body.get("consignment_id") or body.get("id") or "")
        tracking = str(body.get("tracking_code") or cid)
        if not cid and not tracking:
            raise CourierGatewayError("Steadfast booking response did not include a consignment/tracking code.", code="steadfast_booking_invalid", response=data)
        provider_status = str(body.get("status") or "in_review")
        return CourierResult(external_id=cid, tracking_code=tracking, provider_status=provider_status, status=self._map_status(provider_status), message=str(data.get("message") or "Booked with Steadfast"), raw={"request": payload, "response": data})

    @staticmethod
    def _map_status(value: str) -> str:
        s = (value or "").lower().replace("-", "_").replace(" ", "_")
        if s in {"delivered", "delivered_approval_pending"}:
            return "delivered"
        # Partial delivery requires merchant review; do not auto-complete the full order.
        if "partial_delivered" in s:
            return "in_transit"
        if "return" in s:
            return "returned"
        if "cancel" in s:
            return "cancelled"
        if "pickup" in s or "picked" in s:
            return "picked"
        if s in {"pending", "in_review"}:
            return "booked"
        return "in_transit"

    def track(self, shipment) -> CourierResult:
        if shipment.tracking_code:
            url = f"{self.base_url}/status_by_trackingcode/{shipment.tracking_code}"
        elif shipment.external_id:
            url = f"{self.base_url}/status_by_cid/{shipment.external_id}"
        else:
            raise CourierGatewayError("Shipment has no Steadfast tracking identifier.", code="tracking_id_missing")
        data = self._request("GET", url, headers=self._headers())
        provider_status = str(data.get("delivery_status") or (data.get("data") or {}).get("delivery_status") or "")
        return CourierResult(external_id=shipment.external_id, tracking_code=shipment.tracking_code, provider_status=provider_status, status=self._map_status(provider_status), message=provider_status, raw=data)

    def create_return_request(self, shipment, *, reason: str = "") -> dict[str, Any]:
        payload = {"reason": reason or "Return requested from commerce dashboard"}
        if shipment.external_id: payload["consignment_id"] = shipment.external_id
        elif shipment.tracking_code: payload["tracking_code"] = shipment.tracking_code
        else: payload["invoice"] = shipment.order.order_number
        return self._request("POST", f"{self.base_url}/create_return_request", json=payload, headers=self._headers())
