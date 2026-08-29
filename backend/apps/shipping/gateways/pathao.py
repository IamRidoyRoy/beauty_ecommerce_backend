from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Any

from .base import BaseCourierAdapter, CourierGatewayError, CourierResult



def _pathao_phone(value: str) -> str:
    """Pathao expects Bangladeshi mobile numbers as 01XXXXXXXXX (11 digits)."""
    digits = re.sub(r"\D", "", str(value or ""))
    if digits.startswith("880") and len(digits) == 13:
        digits = "0" + digits[3:]
    elif digits.startswith("88") and len(digits) == 13:
        digits = digits[2:]
    elif len(digits) == 10 and digits.startswith("1"):
        digits = "0" + digits
    if not re.fullmatch(r"01[3-9]\d{8}", digits):
        raise CourierGatewayError(
            "Pathao requires an 11-digit Bangladesh mobile number (01XXXXXXXXX). "
            f"Order phone is {value!s}.",
            code="pathao_invalid_phone",
        )
    return digits


def _pathao_address(address: dict[str, Any]) -> str:
    # Checkout stores address, thana and district separately. Pathao needs a
    # descriptive 10-220 character recipient address, so combine them.
    values = [
        address.get("address") or address.get("full_address") or address.get("street"),
        address.get("thana") or address.get("area"),
        address.get("district"),
    ]
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip().strip(",")
        key = text.lower()
        if text and key not in seen:
            parts.append(text)
            seen.add(key)
    result = ", ".join(parts).strip()[:220]
    if len(result) < 10:
        raise CourierGatewayError(
            "Pathao requires a recipient address of at least 10 characters. Update the order shipping address before submitting.",
            code="pathao_invalid_address",
        )
    return result


def _num(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _pathao_amount_to_collect(value: Any) -> int:
    """Return Pathao's COD amount as a JSON integer in whole BDT.

    Pathao rejects decimal JSON values (for example 709.0 / 2577.50) for
    ``amount_to_collect``. The commerce system intentionally keeps Decimal
    order totals for accounting, so normalize only the provider payload and
    use conventional BDT half-up rounding.
    """
    try:
        amount = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        raise CourierGatewayError(
            "Pathao amount to collect is invalid. Check the order total before submitting.",
            code="pathao_invalid_cod_amount",
        )
    if amount < 0:
        raise CourierGatewayError(
            "Pathao amount to collect cannot be negative.",
            code="pathao_invalid_cod_amount",
        )
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


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
        data = self._request("GET", f"{self.base_url}/aladdin/api/v1/stores", headers=self._headers())
        # A successful token is not enough: the configured pickup store must
        # belong to the selected Sandbox/Live merchant account.
        container = data.get("data") if isinstance(data, dict) else None
        rows = container.get("data") if isinstance(container, dict) else container
        if isinstance(rows, dict):
            rows = rows.get("stores") or rows.get("data") or []
        if isinstance(rows, list):
            configured = str(self.values.get("store_id") or "").strip()
            available = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                sid = row.get("store_id") or row.get("id")
                if sid not in (None, ""):
                    available.append(str(sid))
            if configured and available and configured not in available:
                preview = ", ".join(available[:8])
                raise CourierGatewayError(
                    f"Pathao connection works, but Pickup Store ID {configured} is not available in this {self.runtime.environment} account. "
                    f"Available Store ID(s): {preview}.",
                    code="pathao_store_not_found",
                    response=data,
                )
        return data

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
            "recipient_name": order.customer_name.strip()[:100],
            "recipient_phone": _pathao_phone(order.customer_phone),
            "recipient_address": _pathao_address(address),
            "delivery_type": int(options.get("delivery_type") or 48),
            "item_type": int(options.get("item_type") or 2),
            "special_instruction": str(options.get("instruction") or order.notes or "")[:250],
            "item_quantity": max(qty, 1),
            "item_weight": max(weight, 0.5),
            "amount_to_collect": _pathao_amount_to_collect(cod_amount),
            "item_description": descriptions,
        }
        if len(payload["recipient_name"]) < 3:
            raise CourierGatewayError("Pathao requires recipient name to be at least 3 characters.", code="pathao_invalid_recipient_name")
        if not (0.5 <= payload["item_weight"] <= 10):
            raise CourierGatewayError("Pathao parcel weight must be between 0.5 and 10 kg.", code="pathao_invalid_weight")
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
        if "partial" in s and "deliver" in s:
            return "in_transit"
        if ("delivered" in s or s in {"delivery_completed", "delivery_success", "successful_delivery", "completed"}):
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
