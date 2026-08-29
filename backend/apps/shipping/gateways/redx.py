from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any

from .base import BaseCourierAdapter, CourierGatewayError, CourierResult


class RedXAdapter(BaseCourierAdapter):
    provider = "redx"
    supports_cancel = True

    def _headers(self):
        token = str(self.values["access_token"])
        if not token.lower().startswith("bearer "):
            token = f"Bearer {token}"
        return {"API-ACCESS-TOKEN": token, "Content-Type": "application/json", "Accept": "application/json"}

    def test_connection(self) -> dict[str, Any]:
        return self._request("GET", f"{self.base_url}/areas", headers=self._headers())

    @staticmethod
    def _norm(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()

    def _resolve_area(self, order, options: dict[str, Any]) -> tuple[str, int]:
        if options.get("delivery_area_id"):
            return str(options.get("delivery_area") or ""), int(options["delivery_area_id"])
        address = order.shipping_address_snapshot or {}
        candidates = [address.get("thana"), address.get("area"), address.get("district")]
        candidates = [self._norm(str(x)) for x in candidates if x]
        data = self._request("GET", f"{self.base_url}/areas", headers=self._headers())
        rows = data.get("areas") or data.get("data") or []
        if isinstance(rows, dict): rows = rows.get("areas") or rows.get("data") or []
        best = None
        for row in rows if isinstance(rows, list) else []:
            name = self._norm(str(row.get("name") or ""))
            for token in candidates:
                if token and (token == name or token in name or name in token):
                    best = row
                    if token == name: break
            if best and any(self._norm(str(best.get("name") or "")) == t for t in candidates): break
        if not best:
            raise CourierGatewayError("RedX delivery area could not be matched automatically. Provide delivery_area_id when booking this order.", code="redx_area_required")
        return str(best.get("name") or ""), int(best.get("id"))

    def create_shipment(self, order, *, options=None) -> CourierResult:
        options = options or {}
        address = order.shipping_address_snapshot or {}
        area_name, area_id = self._resolve_area(order, options)
        latest_payment = order.payments.order_by("-created_at").first()
        cod_amount = order.total if latest_payment and latest_payment.method == "cod" and order.payment_status != "paid" else Decimal("0")
        items = [{"name": x.product_name_snapshot, "sku": x.sku_snapshot, "quantity": x.quantity, "price": str(x.unit_price)} for x in order.items.all()]
        weight = int(float(options.get("weight_grams") or self.values.get("default_weight_grams") or 500))
        payload = {
            "customer_name": order.customer_name[:100],
            "customer_phone": order.customer_phone,
            "delivery_area": area_name,
            "delivery_area_id": area_id,
            "customer_address": str(address.get("address") or address.get("full_address") or address.get("street") or "")[:250],
            "merchant_invoice_id": order.order_number,
            "cash_collection_amount": float(cod_amount),
            "parcel_weight": max(weight, 1),
            "instruction": str(options.get("instruction") or order.notes or "")[:250],
            "value": float(order.total),
            "pickup_store_id": int(options.get("pickup_store_id") or self.values["pickup_store_id"]),
            "parcel_details_json": json.dumps(items, ensure_ascii=False),
        }
        if not payload["customer_address"]:
            raise CourierGatewayError("Order shipping address is missing.", code="invalid_shipping_address")
        data = self._request("POST", f"{self.base_url}/parcel", json=payload, headers=self._headers())
        body = data.get("parcel") or data.get("data") or data
        tracking = str(body.get("tracking_id") or body.get("trackingId") or body.get("id") or "")
        if not tracking:
            raise CourierGatewayError("RedX booking response did not include a tracking ID.", code="redx_booking_invalid", response=data)
        provider_status = str(body.get("status") or "pickup-pending")
        return CourierResult(external_id=tracking, tracking_code=tracking, provider_status=provider_status, status=self._map_status(provider_status), message=str(data.get("message") or "Booked with RedX"), raw={"request": payload, "response": data})

    @staticmethod
    def _map_status(value: str) -> str:
        s = (value or "").lower().replace("_", "-").replace(" ", "-")
        if "return" in s:
            return "returned"
        if "cancel" in s:
            return "cancelled"
        if "fail" in s:
            return "failed"
        if "out-for-delivery" in s or "delivery-in-progress" in s:
            return "out_for_delivery"
        if s in {"delivered", "delivery-completed", "completed"} or s.endswith("-delivered"):
            return "delivered"
        if "transit" in s or "hub" in s or "sorting" in s:
            return "in_transit"
        if "picked" in s or "pickup-complete" in s:
            return "picked"
        return "booked"

    def track(self, shipment) -> CourierResult:
        tracking = shipment.tracking_code or shipment.external_id
        if not tracking:
            raise CourierGatewayError("Shipment has no RedX tracking ID.", code="tracking_id_missing")
        data = self._request("GET", f"{self.base_url}/parcel/info/{tracking}", headers=self._headers())
        body = data.get("parcel") or data.get("data") or data
        provider_status = str(body.get("status") or "")
        return CourierResult(external_id=str(tracking), tracking_code=str(tracking), provider_status=provider_status, status=self._map_status(provider_status), message=provider_status, raw=data)

    def cancel_shipment(self, shipment, *, reason: str = "") -> CourierResult:
        tracking = shipment.tracking_code or shipment.external_id
        if not tracking:
            raise CourierGatewayError("Shipment has no RedX tracking ID.", code="tracking_id_missing")
        payload = {
            "entity_type": "parcel-tracking-id",
            "entity_id": tracking,
            "update_details": {"property_name": "status", "new_value": "cancelled"},
            "reason": reason or "Cancelled from merchant dashboard",
        }
        endpoint = str(self.values.get("cancel_endpoint") or "").strip()
        if not endpoint:
            raise CourierGatewayError(
                "RedX cancellation endpoint is not configured for this merchant contract.",
                code="cancel_endpoint_not_configured",
            )
        url = endpoint if endpoint.startswith(("http://", "https://")) else f"{self.base_url}/{endpoint.lstrip('/')}"
        data = self._request("PATCH", url, json=payload, headers=self._headers())
        return CourierResult(external_id=str(tracking), tracking_code=str(tracking), provider_status="cancelled", status="cancelled", message=str(data.get("message") or "Cancellation submitted to RedX"), raw=data)
