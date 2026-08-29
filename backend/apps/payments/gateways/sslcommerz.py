from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from .base import GatewayClient, InitiationResult, PaymentGatewayError, VerificationResult


class SSLCommerzGateway(GatewayClient):
    provider = "sslcommerz"

    @property
    def base_url(self) -> str:
        configured = str(self.value("base_url", "")).strip()
        if configured:
            return configured.rstrip("/")
        return "https://sandbox.sslcommerz.com" if self.sandbox else "https://securepay.sslcommerz.com"

    def _credentials(self) -> tuple[str, str]:
        store_id = str(self.value("store_id", "")).strip()
        store_password = str(self.value("store_password", "")).strip()
        if not store_id or not store_password:
            raise PaymentGatewayError("SSLCOMMERZ credentials are not configured.", code="gateway_not_configured")
        return store_id, store_password

    def initiate(self, *, payment, callback_url: str) -> InitiationResult:
        store_id, store_password = self._credentials()
        order = payment.order
        merchant_reference = f"{order.order_number}-{uuid.uuid4().hex[:8].upper()}"[:30]
        address = order.shipping_address_snapshot or {}
        email = getattr(order.user, "email", "") or "customer@example.com"
        product_names = ", ".join(order.items.values_list("product_name_snapshot", flat=True)[:5]) or "Beauty products"
        product_categories = ", ".join(
            order.items.exclude(product__category__name="").values_list("product__category__name", flat=True).distinct()[:5]
        ) or "Beauty"
        callback_root = callback_url.rstrip("/")
        payload = {
            "store_id": store_id,
            "store_passwd": store_password,
            "total_amount": self.money(payment.amount),
            "currency": payment.currency or "BDT",
            "tran_id": merchant_reference,
            "success_url": f"{callback_root}/success/",
            "fail_url": f"{callback_root}/fail/",
            "cancel_url": f"{callback_root}/cancel/",
            "ipn_url": f"{callback_root}/ipn/",
            "cus_name": order.customer_name,
            "cus_email": email,
            "cus_add1": address.get("address", "Dhaka"),
            "cus_city": address.get("district", "Dhaka"),
            "cus_state": address.get("district", "Dhaka"),
            "cus_postcode": address.get("postcode", "1000"),
            "cus_country": "Bangladesh",
            "cus_phone": order.customer_phone,
            "shipping_method": "YES",
            "ship_name": order.customer_name,
            "ship_add1": address.get("address", "Dhaka"),
            "ship_city": address.get("district", "Dhaka"),
            "ship_state": address.get("district", "Dhaka"),
            "ship_postcode": address.get("postcode", "1000"),
            "ship_country": "Bangladesh",
            "product_name": product_names[:255],
            "product_category": product_categories[:100],
            "product_profile": "general",
            "value_a": order.order_number,
            "value_b": str(payment.public_token),
        }
        response = self._request("POST",
            f"{self.base_url}/gwprocess/v4/api.php",
            data=payload,
            timeout=self.timeout,
        )
        data = self._json_response(response)
        if str(data.get("status", "")).upper() != "SUCCESS" or not data.get("GatewayPageURL"):
            raise PaymentGatewayError(
                str(data.get("failedreason") or data.get("status") or "SSLCOMMERZ session creation failed."),
                code="initiation_failed",
                payload=data,
            )
        return InitiationResult(
            redirect_url=data["GatewayPageURL"],
            gateway_reference=str(data.get("sessionkey", "")),
            merchant_reference=merchant_reference,
            raw={k: v for k, v in data.items() if k not in {"store_passwd"}},
        )

    def _validation(self, val_id: str) -> dict[str, Any]:
        store_id, store_password = self._credentials()
        response = self._request("GET",
            f"{self.base_url}/validator/api/validationserverAPI.php",
            params={
                "val_id": val_id,
                "store_id": store_id,
                "store_passwd": store_password,
                "format": "json",
            },
            timeout=self.timeout,
        )
        return self._json_response(response)

    def verify(self, *, payment, callback_payload: dict[str, Any] | None = None) -> VerificationResult:
        callback_payload = callback_payload or {}
        val_id = str(callback_payload.get("val_id") or "").strip()
        merchant_reference = str((payment.metadata or {}).get("merchant_reference") or callback_payload.get("tran_id") or "").strip()
        if val_id:
            data = self._validation(val_id)
        elif merchant_reference:
            store_id, store_password = self._credentials()
            response = self._request("GET",
                f"{self.base_url}/validator/api/merchantTransIDvalidationAPI.php",
                params={"tran_id": merchant_reference, "store_id": store_id, "store_passwd": store_password, "format": "json"},
                timeout=self.timeout,
            )
            envelope = self._json_response(response)
            elements = envelope.get("element") or []
            if isinstance(elements, dict):
                elements = [elements]
            data = next((row for row in reversed(elements) if str(row.get("status", "")).upper() in {"VALID", "VALIDATED"}), elements[-1] if elements else envelope)
        else:
            raise PaymentGatewayError("SSLCOMMERZ payment has no validation or merchant transaction reference.", code="missing_gateway_reference")

        gateway_status = str(data.get("status", "")).upper()
        returned_reference = str(data.get("tran_id") or merchant_reference)
        if merchant_reference and returned_reference and returned_reference != merchant_reference:
            raise PaymentGatewayError("SSLCOMMERZ transaction reference mismatch.", code="transaction_reference_mismatch", payload=data)

        try:
            amount = Decimal(str(data.get("amount"))) if data.get("amount") not in (None, "") else None
        except (InvalidOperation, TypeError):
            amount = None
        if amount is not None and amount != payment.amount:
            raise PaymentGatewayError("SSLCOMMERZ amount mismatch.", code="amount_mismatch", payload=data)

        currency = str(data.get("currency") or payment.currency or "BDT").upper()
        if currency != (payment.currency or "BDT").upper():
            raise PaymentGatewayError("SSLCOMMERZ currency mismatch.", code="currency_mismatch", payload=data)

        if gateway_status in {"VALID", "VALIDATED"}:
            return VerificationResult(
                status="paid",
                transaction_id=str(data.get("bank_tran_id") or data.get("tran_id") or ""),
                gateway_reference=str(data.get("val_id") or payment.gateway_reference or ""),
                amount=amount,
                currency=currency,
                raw=data,
            )
        if gateway_status in {"FAILED", "EXPIRED", "INVALID_TRANSACTION"}:
            status = "failed"
        elif gateway_status in {"CANCELLED", "UNATTEMPTED"}:
            status = "cancelled"
        else:
            status = "pending"
        return VerificationResult(
            status=status,
            transaction_id=str(data.get("bank_tran_id") or ""),
            gateway_reference=str(data.get("val_id") or payment.gateway_reference or ""),
            amount=amount,
            currency=currency,
            failure_code=gateway_status,
            failure_message=str(data.get("errorReason") or data.get("failedreason") or ""),
            raw=data,
        )
