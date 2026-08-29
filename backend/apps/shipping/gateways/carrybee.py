from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from .base import BaseCourierAdapter, CourierGatewayError, CourierResult


class CarryBeeAdapter(BaseCourierAdapter):
    """CarryBee Developers API v2 adapter.

    Credentials are supplied by the dashboard-managed courier configuration and
    are never exposed to customer-facing APIs.
    """

    provider = "carrybee"
    supports_cancel = True

    def _headers(self) -> dict[str, str]:
        return {
            "Client-ID": str(self.values["client_id"]),
            "Client-Secret": str(self.values["client_secret"]),
            "Client-Context": str(self.values["client_context"]),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @staticmethod
    def _norm(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()

    @staticmethod
    def _data(value: Any) -> Any:
        if isinstance(value, dict) and "data" in value:
            return value.get("data")
        return value

    @classmethod
    def _rows(cls, value: Any, *keys: str) -> list[dict[str, Any]]:
        current = cls._data(value)
        if isinstance(current, list):
            return [row for row in current if isinstance(row, dict)]
        if isinstance(current, dict):
            for key in keys:
                candidate = current.get(key)
                if isinstance(candidate, list):
                    return [row for row in candidate if isinstance(row, dict)]
                candidate = cls._data(candidate)
                if isinstance(candidate, list):
                    return [row for row in candidate if isinstance(row, dict)]
        return []

    @staticmethod
    def _phone(value: str) -> str:
        digits = re.sub(r"\D+", "", value or "")
        if digits.startswith("880") and len(digits) >= 13:
            digits = digits[2:]
        return digits

    @staticmethod
    def _first_id(row: dict[str, Any] | None, *keys: str) -> int | None:
        if not row:
            return None
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                try:
                    return int(value)
                except (TypeError, ValueError):
                    continue
        return None

    @classmethod
    def _best_match(cls, rows: list[dict[str, Any]], candidates: list[str]) -> dict[str, Any] | None:
        tokens = [cls._norm(v) for v in candidates if cls._norm(v)]
        exact = None
        partial = None
        for row in rows:
            name = cls._norm(str(row.get("name") or row.get("title") or row.get("city_name") or row.get("zone_name") or row.get("area_name") or ""))
            if not name:
                continue
            for token in tokens:
                if name == token:
                    exact = row
                    break
                if token in name or name in token:
                    partial = partial or row
            if exact:
                break
        return exact or partial

    def test_connection(self) -> dict[str, Any]:
        return self._request("GET", f"{self.base_url}/api/v2/cities", headers=self._headers())

    def _address_text(self, order) -> str:
        address = order.shipping_address_snapshot or {}
        values = [
            address.get("address") or address.get("full_address") or address.get("street"),
            address.get("thana") or address.get("area"),
            address.get("district"),
        ]
        deduped: list[str] = []
        seen = set()
        for value in values:
            text = str(value or "").strip()
            key = text.lower()
            if text and key not in seen:
                deduped.append(text)
                seen.add(key)
        return ", ".join(deduped)

    def _resolve_from_address_details(self, query: str) -> tuple[int | None, int | None, int | None]:
        if not query:
            return None, None, None
        try:
            response = self._request(
                "POST",
                f"{self.base_url}/api/v2/address-details",
                json={"query": query},
                headers=self._headers(),
            )
        except CourierGatewayError:
            return None, None, None
        body = self._data(response)
        if isinstance(body, dict) and isinstance(body.get("address"), dict):
            body = body["address"]
        if not isinstance(body, dict):
            return None, None, None
        city_id = self._first_id(body, "city_id", "cityId")
        zone_id = self._first_id(body, "zone_id", "zoneId")
        area_id = self._first_id(body, "area_id", "areaId")
        city = body.get("city") if isinstance(body.get("city"), dict) else None
        zone = body.get("zone") if isinstance(body.get("zone"), dict) else None
        area = body.get("area") if isinstance(body.get("area"), dict) else None
        city_id = city_id or self._first_id(city, "id", "city_id")
        zone_id = zone_id or self._first_id(zone, "id", "zone_id")
        area_id = area_id or self._first_id(area, "id", "area_id")
        return city_id, zone_id, area_id

    def _resolve_by_lists(self, order) -> tuple[int | None, int | None, int | None]:
        address = order.shipping_address_snapshot or {}
        district = str(address.get("district") or "")
        thana = str(address.get("thana") or address.get("area") or "")
        street = str(address.get("address") or address.get("full_address") or "")

        cities_response = self._request("GET", f"{self.base_url}/api/v2/cities", headers=self._headers())
        city = self._best_match(self._rows(cities_response, "cities"), [district, street])
        city_id = self._first_id(city, "id", "city_id")
        if not city_id:
            return None, None, None

        zones_response = self._request("GET", f"{self.base_url}/api/v2/cities/{city_id}/zones", headers=self._headers())
        zone = self._best_match(self._rows(zones_response, "zones"), [thana, street, district])
        zone_id = self._first_id(zone, "id", "zone_id")
        if not zone_id:
            return city_id, None, None

        area_id = None
        try:
            areas_response = self._request(
                "GET",
                f"{self.base_url}/api/v2/cities/{city_id}/zones/{zone_id}/areas",
                headers=self._headers(),
            )
            area = self._best_match(self._rows(areas_response, "areas"), [thana, street])
            area_id = self._first_id(area, "id", "area_id")
        except CourierGatewayError:
            # CarryBee area_id is optional; city and zone are sufficient for booking.
            pass
        return city_id, zone_id, area_id

    def _resolve_location(self, order, options: dict[str, Any]) -> tuple[int, int, int | None]:
        try:
            manual_city = int(options["city_id"]) if options.get("city_id") not in (None, "") else None
            manual_zone = int(options["zone_id"]) if options.get("zone_id") not in (None, "") else None
            manual_area = int(options["area_id"]) if options.get("area_id") not in (None, "") else None
        except (TypeError, ValueError) as exc:
            raise CourierGatewayError("CarryBee city/zone/area IDs must be numeric.", code="carrybee_invalid_location_id") from exc
        if manual_city and manual_zone:
            return manual_city, manual_zone, manual_area

        query = self._address_text(order)
        city_id, zone_id, area_id = self._resolve_from_address_details(query)
        if not (city_id and zone_id):
            fallback_city, fallback_zone, fallback_area = self._resolve_by_lists(order)
            city_id = city_id or fallback_city
            zone_id = zone_id or fallback_zone
            area_id = area_id or fallback_area

        city_id = manual_city or city_id
        zone_id = manual_zone or zone_id
        area_id = manual_area or area_id
        if not (city_id and zone_id):
            raise CourierGatewayError(
                "CarryBee city/zone could not be resolved automatically. Provide city_id and zone_id from the CarryBee merchant location list when booking this order.",
                code="carrybee_location_required",
            )
        return int(city_id), int(zone_id), int(area_id) if area_id else None

    @staticmethod
    def _map_status(value: str) -> str:
        status = (value or "").lower().replace("_", "-").replace(" ", "-")
        if "returned-to-merchant" in status or "return" in status:
            return "returned"
        if "cancel" in status:
            return "cancelled"
        if "delivery-failed" in status or "fail" in status:
            return "failed"
        if "delivered" in status or status in {"complete", "completed"}:
            return "delivered"
        if "assigned-for-delivery" in status or "out-for-delivery" in status:
            return "out_for_delivery"
        if any(token in status for token in ("in-transit", "sorting", "last-mile", "hub")):
            return "in_transit"
        if "picked" in status:
            return "picked"
        return "booked"

    def create_shipment(self, order, *, options=None) -> CourierResult:
        options = options or {}
        address = order.shipping_address_snapshot or {}
        recipient_address = self._address_text(order)
        if not recipient_address:
            raise CourierGatewayError("Order shipping address is missing.", code="invalid_shipping_address")

        city_id, zone_id, area_id = self._resolve_location(order, options)
        latest_payment = order.payments.order_by("-created_at").first()
        cod_amount = order.total if latest_payment and latest_payment.method == "cod" and order.payment_status != "paid" else Decimal("0")
        items = list(order.items.all())
        product_description = ", ".join(
            f"{item.product_name_snapshot} x{item.quantity}" for item in items[:8]
        )[:500]
        quantity = sum(int(item.quantity) for item in items) or 1

        try:
            delivery_type = int(options.get("delivery_type") or self.values.get("default_delivery_type") or 1)
            product_type = int(options.get("product_type") or self.values.get("default_product_type") or 1)
            weight_grams = int(float(options.get("weight_grams") or self.values.get("default_weight_grams") or 500))
            store_id = int(options.get("store_id") or self.values["store_id"])
        except (TypeError, ValueError) as exc:
            raise CourierGatewayError("CarryBee store, delivery type, product type and weight must be numeric.", code="carrybee_invalid_booking_option") from exc

        payload: dict[str, Any] = {
            "store_id": store_id,
            "merchant_order_id": order.order_number,
            "delivery_type": delivery_type,
            "product_type": product_type,
            "recipient_phone": self._phone(order.customer_phone),
            "recipient_name": order.customer_name[:120],
            "recipient_address": recipient_address[:500],
            "city_id": city_id,
            "zone_id": zone_id,
            "special_instruction": str(options.get("instruction") or order.notes or "")[:500],
            "product_description": product_description,
            "item_weight": max(weight_grams, 1),
            "item_quantity": max(quantity, 1),
            "collectable_amount": float(cod_amount),
        }
        if cod_amount > 0:
            payload["collectable_amount"] = float(cod_amount)
        else:
            payload.pop("collectable_amount", None)
        if area_id:
            payload["area_id"] = area_id

        data = self._request("POST", f"{self.base_url}/api/v2/orders", json=payload, headers=self._headers())
        body: Any = self._data(data)
        if isinstance(body, dict) and isinstance(body.get("order"), dict):
            body = body["order"]
        if not isinstance(body, dict):
            body = {}
        consignment = str(
            body.get("consignment_id")
            or body.get("consignmentId")
            or body.get("tracking_code")
            or body.get("tracking_id")
            or body.get("id")
            or ""
        )
        if not consignment:
            raise CourierGatewayError(
                "CarryBee booking response did not include a consignment ID.",
                code="carrybee_booking_invalid",
                response=data,
            )
        provider_status = str(body.get("transfer_status") or body.get("status") or body.get("order_status") or "pending")
        message = str(data.get("message") or body.get("message") or "Booked with CarryBee") if isinstance(data, dict) else "Booked with CarryBee"
        return CourierResult(
            external_id=consignment,
            tracking_code=consignment,
            provider_status=provider_status,
            status=self._map_status(provider_status),
            message=message,
            raw={"request": payload, "response": data},
        )

    def track(self, shipment) -> CourierResult:
        consignment = shipment.tracking_code or shipment.external_id
        if not consignment:
            raise CourierGatewayError("Shipment has no CarryBee consignment ID.", code="tracking_id_missing")
        data = self._request(
            "GET",
            f"{self.base_url}/api/v2/orders/{consignment}/details",
            headers=self._headers(),
        )
        body: Any = self._data(data)
        if isinstance(body, dict) and isinstance(body.get("order"), dict):
            body = body["order"]
        if not isinstance(body, dict):
            body = {}
        provider_status = str(
            body.get("transfer_status")
            or body.get("status")
            or body.get("order_status")
            or body.get("event")
            or ""
        )
        return CourierResult(
            external_id=str(consignment),
            tracking_code=str(consignment),
            provider_status=provider_status,
            status=self._map_status(provider_status),
            message=str(body.get("message") or provider_status),
            raw=data if isinstance(data, dict) else {"response": data},
        )

    def cancel_shipment(self, shipment, *, reason: str = "") -> CourierResult:
        consignment = shipment.tracking_code or shipment.external_id
        if not consignment:
            raise CourierGatewayError("Shipment has no CarryBee consignment ID.", code="tracking_id_missing")
        payload = {"cancellation_reason": reason or "Cancelled from merchant dashboard"}
        data = self._request(
            "POST",
            f"{self.base_url}/api/v2/orders/{consignment}/cancel",
            json=payload,
            headers=self._headers(),
        )
        body: Any = self._data(data)
        provider_status = "cancelled"
        if isinstance(body, dict):
            provider_status = str(body.get("transfer_status") or body.get("status") or provider_status)
        return CourierResult(
            external_id=str(consignment),
            tracking_code=str(consignment),
            provider_status=provider_status,
            status="cancelled",
            message=str(data.get("message") or "Cancellation submitted to CarryBee") if isinstance(data, dict) else "Cancellation submitted to CarryBee",
            raw=data if isinstance(data, dict) else {"response": data},
        )
