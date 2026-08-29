from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.cache import cache

from .base import GatewayClient, InitiationResult, PaymentGatewayError, VerificationResult


class BKashGateway(GatewayClient):
    provider = "bkash"

    @property
    def base_url(self) -> str:
        configured = str(self.value("base_url", "")).strip()
        if configured:
            return configured.rstrip("/")
        return "https://tokenized.sandbox.bka.sh/v1.2.0-beta" if self.sandbox else "https://tokenized.pay.bka.sh/v1.2.0-beta"

    def _credentials(self) -> tuple[str, str, str, str]:
        app_key = str(self.value("app_key", "")).strip()
        app_secret = str(self.value("app_secret", "")).strip()
        username = str(self.value("username", "")).strip()
        password = str(self.value("password", "")).strip()
        if not all((app_key, app_secret, username, password)):
            raise PaymentGatewayError("bKash credentials are not configured.", code="gateway_not_configured")
        return app_key, app_secret, username, password

    def _token(self) -> str:
        app_key, app_secret, username, password = self._credentials()
        cache_key = f"payment:bkash:token:{app_key[-8:]}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        response = self._request("POST",
            f"{self.base_url}/tokenized/checkout/token/grant",
            headers={"username": username, "password": password, "accept": "application/json", "content-type": "application/json"},
            json={"app_key": app_key, "app_secret": app_secret},
            timeout=self.timeout,
        )
        data = self._json_response(response)
        token = str(data.get("id_token") or "")
        if not token:
            raise PaymentGatewayError(str(data.get("statusMessage") or data.get("errorMessage") or "bKash token grant failed."), code="authentication_failed", payload=data)
        expires_in = int(data.get("expires_in") or 3500)
        cache.set(cache_key, token, max(60, expires_in - 60))
        return token

    def _headers(self) -> dict[str, str]:
        app_key, _, _, _ = self._credentials()
        return {
            "authorization": self._token(),
            "x-app-key": app_key,
            "accept": "application/json",
            "content-type": "application/json",
        }

    def initiate(self, *, payment, callback_url: str) -> InitiationResult:
        order = payment.order
        response = self._request("POST",
            f"{self.base_url}/tokenized/checkout/create",
            headers=self._headers(),
            json={
                "mode": "0011",
                "payerReference": order.customer_phone,
                "callbackURL": callback_url,
                "amount": self.money(payment.amount),
                "currency": payment.currency or "BDT",
                "intent": "sale",
                "merchantInvoiceNumber": order.order_number,
            },
            timeout=self.timeout,
        )
        data = self._json_response(response)
        payment_id = str(data.get("paymentID") or data.get("paymentId") or "")
        redirect_url = str(data.get("bkashURL") or data.get("bKashURL") or "")
        if not payment_id or not redirect_url:
            raise PaymentGatewayError(str(data.get("statusMessage") or data.get("errorMessage") or "bKash payment creation failed."), code="initiation_failed", payload=data)
        return InitiationResult(
            redirect_url=redirect_url,
            gateway_reference=payment_id,
            merchant_reference=order.order_number,
            raw=data,
        )

    def _execute(self, payment_id: str) -> dict[str, Any]:
        response = self._request("POST",
            f"{self.base_url}/tokenized/checkout/execute",
            headers=self._headers(),
            json={"paymentID": payment_id},
            timeout=self.timeout,
        )
        return self._json_response(response)

    def _query(self, payment_id: str) -> dict[str, Any]:
        response = self._request("POST",
            f"{self.base_url}/tokenized/checkout/payment/status",
            headers=self._headers(),
            json={"paymentID": payment_id},
            timeout=self.timeout,
        )
        return self._json_response(response)

    def verify(self, *, payment, callback_payload: dict[str, Any] | None = None) -> VerificationResult:
        callback_payload = callback_payload or {}
        payment_id = str(callback_payload.get("paymentID") or callback_payload.get("paymentId") or payment.gateway_reference or "").strip()
        if not payment_id:
            raise PaymentGatewayError("bKash payment ID is missing.", code="missing_gateway_reference")
        if payment.gateway_reference and payment_id != payment.gateway_reference:
            raise PaymentGatewayError("bKash payment ID mismatch.", code="transaction_reference_mismatch")

        callback_status = str(callback_payload.get("status") or "").lower()
        if callback_status in {"cancel", "cancelled"}:
            data = self._query(payment_id)
        elif callback_status in {"failure", "failed"}:
            data = self._query(payment_id)
        elif callback_status in {"success", "successful"}:
            data = self._execute(payment_id)
            if str(data.get("transactionStatus") or "").upper() not in {"COMPLETED", "SUCCESS"}:
                data = self._query(payment_id)
        else:
            data = self._query(payment_id)

        status_raw = str(data.get("transactionStatus") or data.get("status") or "").upper()
        invoice = str(data.get("merchantInvoiceNumber") or "")
        if invoice and invoice != payment.order.order_number:
            raise PaymentGatewayError("bKash merchant invoice mismatch.", code="transaction_reference_mismatch", payload=data)
        try:
            amount = Decimal(str(data.get("amount"))) if data.get("amount") not in (None, "") else None
        except (InvalidOperation, TypeError):
            amount = None
        if amount is not None and amount != payment.amount:
            raise PaymentGatewayError("bKash amount mismatch.", code="amount_mismatch", payload=data)
        currency = str(data.get("currency") or payment.currency or "BDT").upper()
        if currency != (payment.currency or "BDT").upper():
            raise PaymentGatewayError("bKash currency mismatch.", code="currency_mismatch", payload=data)

        if status_raw in {"COMPLETED", "SUCCESS"} and data.get("trxID"):
            status = "paid"
        elif status_raw in {"CANCELLED", "CANCELED"} or callback_status in {"cancel", "cancelled"}:
            status = "cancelled"
        elif status_raw in {"FAILED", "FAILURE"} or callback_status in {"failure", "failed"}:
            status = "failed"
        else:
            status = "pending"
        return VerificationResult(
            status=status,
            transaction_id=str(data.get("trxID") or ""),
            gateway_reference=payment_id,
            amount=amount,
            currency=currency,
            failure_code=str(data.get("statusCode") or data.get("errorCode") or status_raw),
            failure_message=str(data.get("statusMessage") or data.get("errorMessage") or ""),
            raw=data,
        )
