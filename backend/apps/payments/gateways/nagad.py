from __future__ import annotations

import base64
import json
import secrets
from decimal import Decimal, InvalidOperation
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.utils import timezone

from .base import GatewayClient, InitiationResult, PaymentGatewayError, VerificationResult


class NagadGateway(GatewayClient):
    provider = "nagad"

    @property
    def base_url(self) -> str:
        value = str(self.value("base_url", "")).strip()
        if not value:
            value = (
                "https://sandboxapi.nagad.com.bd/remote-payment-gateway-1.0/api/dfs"
                if self.sandbox
                else "https://api.nagad.com.bd/remote-payment-gateway-1.0/api/dfs"
            )
        return value.rstrip("/")

    def _credentials(self) -> tuple[str, str, str, str]:
        merchant_id = str(self.value("merchant_id", "")).strip()
        merchant_number = str(self.value("merchant_number", "")).strip()
        private_key = str(self.value("merchant_private_key", "")).strip()
        gateway_public_key = str(self.value("gateway_public_key", "")).strip()
        if not merchant_id or not private_key or not gateway_public_key:
            raise PaymentGatewayError("Nagad credentials are not configured.", code="gateway_not_configured")
        return merchant_id, merchant_number, private_key, gateway_public_key

    @staticmethod
    def _pem(value: str, kind: str) -> bytes:
        text = value.strip().replace("\\n", "\n")
        if "-----BEGIN" in text:
            return text.encode()
        compact = "".join(text.split())
        if kind == "private":
            return f"-----BEGIN PRIVATE KEY-----\n{compact}\n-----END PRIVATE KEY-----\n".encode()
        return f"-----BEGIN PUBLIC KEY-----\n{compact}\n-----END PUBLIC KEY-----\n".encode()

    def _private_key(self):
        _, _, private_key, _ = self._credentials()
        try:
            return serialization.load_pem_private_key(self._pem(private_key, "private"), password=None)
        except Exception as exc:
            # Some merchant portals export PKCS#1 RSA private keys.
            try:
                compact = "".join(private_key.replace("\\n", "\n").split())
                pem = f"-----BEGIN RSA PRIVATE KEY-----\n{compact}\n-----END RSA PRIVATE KEY-----\n".encode()
                return serialization.load_pem_private_key(pem, password=None)
            except Exception as nested:
                raise PaymentGatewayError("Nagad merchant private key is invalid.", code="invalid_gateway_key") from nested

    def _public_key(self):
        _, _, _, gateway_public_key = self._credentials()
        try:
            return serialization.load_pem_public_key(self._pem(gateway_public_key, "public"))
        except Exception as exc:
            raise PaymentGatewayError("Nagad gateway public key is invalid.", code="invalid_gateway_key") from exc

    @staticmethod
    def _compact_json(payload: dict[str, Any]) -> bytes:
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()

    def _encrypt(self, payload: dict[str, Any]) -> str:
        encrypted = self._public_key().encrypt(self._compact_json(payload), padding.PKCS1v15())
        return base64.b64encode(encrypted).decode()

    def _decrypt(self, value: str) -> dict[str, Any]:
        try:
            plaintext = self._private_key().decrypt(base64.b64decode(value), padding.PKCS1v15())
            return json.loads(plaintext.decode())
        except Exception as exc:
            raise PaymentGatewayError("Unable to decrypt Nagad gateway response.", code="invalid_gateway_signature") from exc

    def _sign(self, payload: dict[str, Any]) -> str:
        signature = self._private_key().sign(self._compact_json(payload), padding.PKCS1v15(), hashes.SHA256())
        return base64.b64encode(signature).decode()

    def _headers(self) -> dict[str, str]:
        client_ip = str(self.value("client_ip", "")).strip() or "127.0.0.1"
        return {
            "content-type": "application/json",
            "accept": "application/json",
            "X-KM-Api-Version": str(self.value("api_version", "v-0.2.0")),
            "X-KM-IP-V4": client_ip,
            "X-KM-Client-Type": str(self.value("client_type", "PC_WEB")),
        }

    def initiate(self, *, payment, callback_url: str) -> InitiationResult:
        merchant_id, merchant_number, _, _ = self._credentials()
        order_id = payment.order.order_number.replace("ORD-", "")[:20]
        now = timezone.localtime(timezone.now()).strftime("%Y%m%d%H%M%S")
        challenge = secrets.token_urlsafe(30)[:40]
        sensitive = {"merchantId": merchant_id, "datetime": now, "orderId": order_id, "challenge": challenge}
        init_body = {
            "accountNumber": merchant_number,
            "dateTime": now,
            "sensitiveData": self._encrypt(sensitive),
            "signature": self._sign(sensitive),
        }
        init_response = self._request("POST",
            f"{self.base_url}/check-out/initialize/{merchant_id}/{order_id}",
            headers=self._headers(),
            json=init_body,
            timeout=self.timeout,
        )
        init_data = self._json_response(init_response)
        if init_data.get("reason") or not init_data.get("sensitiveData"):
            raise PaymentGatewayError(str(init_data.get("message") or init_data.get("reason") or "Nagad initialization failed."), code="initiation_failed", payload=init_data)
        decrypted = self._decrypt(str(init_data["sensitiveData"]))
        payment_ref = str(decrypted.get("paymentReferenceId") or "")
        returned_challenge = str(decrypted.get("challenge") or "")
        if not payment_ref or not returned_challenge:
            raise PaymentGatewayError("Nagad initialization response is incomplete.", code="invalid_gateway_response", payload=init_data)

        order_sensitive = {
            "merchantId": merchant_id,
            "orderId": order_id,
            "currencyCode": str(self.value("currency_code", "050")),
            "amount": self.money(payment.amount),
            "challenge": returned_challenge,
        }
        complete_response = self._request("POST",
            f"{self.base_url}/check-out/complete/{payment_ref}",
            headers=self._headers(),
            json={
                "sensitiveData": self._encrypt(order_sensitive),
                "signature": self._sign(order_sensitive),
                "merchantCallbackURL": callback_url,
            },
            timeout=self.timeout,
        )
        complete_data = self._json_response(complete_response)
        redirect_url = str(complete_data.get("callBackUrl") or complete_data.get("callbackUrl") or "")
        if str(complete_data.get("status") or "").lower() != "success" or not redirect_url:
            raise PaymentGatewayError(str(complete_data.get("message") or complete_data.get("reason") or "Nagad checkout creation failed."), code="initiation_failed", payload=complete_data)
        return InitiationResult(
            redirect_url=redirect_url,
            gateway_reference=payment_ref,
            merchant_reference=order_id,
            raw={"initialize": {"paymentReferenceId": payment_ref}, "complete": complete_data},
        )

    def verify(self, *, payment, callback_payload: dict[str, Any] | None = None) -> VerificationResult:
        callback_payload = callback_payload or {}
        payment_ref = str(callback_payload.get("payment_ref_id") or callback_payload.get("paymentRefId") or payment.gateway_reference or "").strip()
        if not payment_ref:
            raise PaymentGatewayError("Nagad payment reference is missing.", code="missing_gateway_reference")
        if payment.gateway_reference and payment_ref != payment.gateway_reference:
            raise PaymentGatewayError("Nagad payment reference mismatch.", code="transaction_reference_mismatch")
        response = self._request("GET", f"{self.base_url}/verify/payment/{payment_ref}", headers=self._headers(), timeout=self.timeout)
        data = self._json_response(response)
        expected_ref = str(data.get("paymentRefId") or data.get("paymentReferenceId") or payment_ref)
        if expected_ref and expected_ref != payment_ref:
            raise PaymentGatewayError("Nagad verification reference mismatch.", code="transaction_reference_mismatch", payload=data)
        try:
            amount = Decimal(str(data.get("amount"))) if data.get("amount") not in (None, "") else None
        except (InvalidOperation, TypeError):
            amount = None
        if amount is not None and amount != payment.amount:
            raise PaymentGatewayError("Nagad amount mismatch.", code="amount_mismatch", payload=data)

        expected_order = str((payment.metadata or {}).get("merchant_reference") or "")
        returned_order = str(data.get("orderId") or "")
        if expected_order and returned_order and expected_order != returned_order:
            raise PaymentGatewayError("Nagad order reference mismatch.", code="transaction_reference_mismatch", payload=data)

        status_raw = str(data.get("status") or callback_payload.get("status") or "").lower()
        status_code = str(data.get("statusCode") or callback_payload.get("status_code") or "")
        paid = status_raw == "success" and status_code in {"000", "00_0000_000", ""} and bool(data.get("issuerPaymentRefNo") or callback_payload.get("issuer_payment_ref"))
        if paid:
            status = "paid"
        elif status_raw in {"cancel", "cancelled", "canceled"}:
            status = "cancelled"
        elif status_raw in {"failed", "failure"} or (status_code and status_code not in {"000", "00_0000_000"}):
            status = "failed"
        else:
            status = "pending"
        return VerificationResult(
            status=status,
            transaction_id=str(data.get("issuerPaymentRefNo") or callback_payload.get("issuer_payment_ref") or ""),
            gateway_reference=payment_ref,
            amount=amount,
            currency="BDT",
            failure_code=status_code,
            failure_message=str(data.get("message") or callback_payload.get("message") or ""),
            raw=data,
        )
