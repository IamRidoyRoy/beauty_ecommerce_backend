from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .gateways import BKashGateway, NagadGateway, PaymentGatewayError, SSLCommerzGateway
from .gateways.base import VerificationResult
from .models import Payment, PaymentReconciliation, PaymentWebhookEvent
from .gateway_config import runtime_config


GATEWAY_METHODS = {
    Payment.Method.SSLCOMMERZ: "sslcommerz",
    Payment.Method.CARD: "sslcommerz",  # backward-compatible card option uses SSLCOMMERZ hosted checkout
    Payment.Method.BKASH: "bkash",
    Payment.Method.NAGAD: "nagad",
}


def create_payment(*, order, method, amount):
    return Payment.objects.create(order=order, method=method, amount=amount, currency="BDT")


def _send_purchase_tracking(payment_id: int):
    try:
        payment = Payment.objects.select_related("order__user").get(pk=payment_id)
        tracking = (payment.metadata or {}).get("tracking") or {}
        if tracking.get("marketing_consent") is False:
            return
        from apps.tracking.models import TrackingSettings
        from apps.tracking.services import send_purchase_for_order

        tracking_settings = TrackingSettings.current()
        if tracking_settings.require_marketing_consent and not tracking.get("marketing_consent", True):
            return
        send_purchase_for_order(order=payment.order, attribution=tracking)
    except Exception:
        # Payment settlement must never be rolled back because marketing tracking failed.
        return


def gateway_provider(payment: Payment) -> str:
    return GATEWAY_METHODS.get(payment.method, "")


def get_gateway(payment: Payment, *, require_active: bool = False, for_initiation: bool = False):
    provider = gateway_provider(payment)
    if not provider:
        raise PaymentGatewayError("This payment method does not use an online gateway.", code="unsupported_payment_method")

    environment = None
    if not for_initiation:
        environment = str((payment.metadata or {}).get("gateway_environment") or "").strip() or None
    config = runtime_config(
        provider,
        require_active=require_active,
        environment=environment,
        allow_legacy_fallback=not for_initiation,
    )
    if provider == "sslcommerz":
        return SSLCommerzGateway(config)
    if provider == "bkash":
        return BKashGateway(config)
    if provider == "nagad":
        return NagadGateway(config)
    raise PaymentGatewayError("This payment method does not use an online gateway.", code="unsupported_payment_method")


def is_online_payment(payment: Payment) -> bool:
    return payment.method in GATEWAY_METHODS


def _merge_metadata(payment: Payment, **values):
    metadata = dict(payment.metadata or {})
    metadata.update(values)
    payment.metadata = metadata


def _public_api_root(request=None) -> str:
    configured = getattr(settings, "PAYMENT_API_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    if request is not None:
        return request.build_absolute_uri("/").rstrip("/")
    raise PaymentGatewayError("PAYMENT_API_BASE_URL must be configured for gateway callbacks.", code="callback_url_not_configured")


def callback_url_for(payment: Payment, *, request=None) -> str:
    root = _public_api_root(request)
    provider = gateway_provider(payment)
    if provider == "sslcommerz":
        return f"{root}/api/v1/payments/sslcommerz/callback"
    if provider == "bkash":
        return f"{root}/api/v1/payments/bkash/callback/"
    if provider == "nagad":
        return f"{root}/api/v1/payments/nagad/callback/"
    raise PaymentGatewayError("No callback URL for this payment method.", code="unsupported_payment_method")


@transaction.atomic
def mark_payment_paid(*, payment, transaction_id="", gateway_reference=""):
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    from apps.orders.models import Order

    order = Order.objects.select_for_update().get(pk=payment.order_id)
    if payment.status == Payment.Status.PAID:
        return payment
    if payment.status in {Payment.Status.PARTIAL_REFUND, Payment.Status.REFUNDED}:
        return payment
    if payment.status not in {Payment.Status.PENDING, Payment.Status.AUTHORIZED, Payment.Status.FAILED, Payment.Status.CANCELLED}:
        raise ValidationError({"payment": "Payment cannot transition to paid."})
    payment.status = Payment.Status.PAID
    payment.transaction_id = transaction_id or payment.transaction_id
    payment.gateway_reference = gateway_reference or payment.gateway_reference
    payment.failure_code = ""
    payment.failure_message = ""
    payment.paid_at = payment.paid_at or timezone.now()
    payment.last_verified_at = timezone.now()
    payment.save(
        update_fields=[
            "status", "transaction_id", "gateway_reference", "failure_code", "failure_message",
            "paid_at", "last_verified_at", "updated_at",
        ]
    )
    order.payment_status = Order.PaymentStatus.PAID
    order.save(update_fields=["payment_status", "updated_at"])
    transaction.on_commit(lambda: _send_purchase_tracking(payment.pk))
    return payment


@transaction.atomic
def mark_payment_unpaid(*, payment, status: str, failure_code="", failure_message=""):
    if status not in {Payment.Status.PENDING, Payment.Status.FAILED, Payment.Status.CANCELLED, Payment.Status.AUTHORIZED}:
        raise ValueError("Unsupported unpaid status")
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    from apps.orders.models import Order

    order = Order.objects.select_for_update().get(pk=payment.order_id)
    if payment.status in {Payment.Status.PAID, Payment.Status.PARTIAL_REFUND, Payment.Status.REFUNDED}:
        return payment
    payment.status = status
    payment.failure_code = failure_code
    payment.failure_message = failure_message
    payment.last_verified_at = timezone.now()
    payment.save(update_fields=["status", "failure_code", "failure_message", "last_verified_at", "updated_at"])
    order.payment_status = Order.PaymentStatus.FAILED if status in {Payment.Status.FAILED, Payment.Status.CANCELLED} else Order.PaymentStatus.PENDING
    order.save(update_fields=["payment_status", "updated_at"])
    return payment


def initiate_gateway_payment(*, payment: Payment, request=None) -> Payment:
    payment = Payment.objects.select_related("order__user").prefetch_related("order__items__product__category").get(pk=payment.pk)
    if payment.status in {Payment.Status.PAID, Payment.Status.PARTIAL_REFUND, Payment.Status.REFUNDED}:
        return payment
    if not is_online_payment(payment):
        return payment

    gateway = get_gateway(payment, require_active=True, for_initiation=True)
    callback_url = callback_url_for(payment, request=request)
    try:
        result = gateway.initiate(payment=payment, callback_url=callback_url)
    except PaymentGatewayError as exc:
        payment.failure_code = exc.code
        payment.failure_message = str(exc)
        _merge_metadata(payment, last_gateway_error=exc.payload)
        payment.save(update_fields=["failure_code", "failure_message", "metadata", "updated_at"])
        raise

    payment.gateway_reference = result.gateway_reference or payment.gateway_reference
    payment.initiated_at = timezone.now()
    payment.failure_code = ""
    payment.failure_message = ""
    _merge_metadata(
        payment,
        provider=gateway.provider,
        gateway_environment=gateway.environment,
        redirect_url=result.redirect_url,
        merchant_reference=result.merchant_reference,
        initiation_response=result.raw,
    )
    payment.save(
        update_fields=[
            "gateway_reference", "initiated_at", "failure_code", "failure_message", "metadata", "updated_at",
        ]
    )
    return payment


def _apply_verification(*, payment: Payment, result: VerificationResult) -> Payment:
    if result.status == Payment.Status.PAID:
        payment = mark_payment_paid(
            payment=payment,
            transaction_id=result.transaction_id,
            gateway_reference=result.gateway_reference,
        )
    else:
        resolved = result.status if result.status in Payment.Status.values else Payment.Status.PENDING
        payment = mark_payment_unpaid(
            payment=payment,
            status=resolved,
            failure_code=result.failure_code,
            failure_message=result.failure_message,
        )
    payment = Payment.objects.get(pk=payment.pk)
    _merge_metadata(payment, verification_response=result.raw)
    payment.gateway_reference = result.gateway_reference or payment.gateway_reference
    payment.transaction_id = result.transaction_id or payment.transaction_id
    payment.save(update_fields=["metadata", "gateway_reference", "transaction_id", "updated_at"])
    return payment


def reconcile_payment(*, payment: Payment, callback_payload: dict[str, Any] | None = None, requested_by=None) -> Payment:
    payment = Payment.objects.select_related("order").get(pk=payment.pk)
    if not is_online_payment(payment):
        return payment
    gateway = get_gateway(payment, require_active=False, for_initiation=False)
    previous_status = payment.status
    try:
        result = gateway.verify(payment=payment, callback_payload=callback_payload or {})
        payment = _apply_verification(payment=payment, result=result)
    except PaymentGatewayError as exc:
        PaymentReconciliation.objects.create(
            payment=payment,
            provider=gateway.provider,
            previous_status=previous_status,
            resolved_status=payment.status,
            success=False,
            response=exc.payload,
            error=f"{exc.code}: {exc}",
            requested_by=requested_by if getattr(requested_by, "is_authenticated", False) else None,
        )
        raise

    PaymentReconciliation.objects.create(
        payment=payment,
        provider=gateway.provider,
        previous_status=previous_status,
        gateway_status=str(result.raw.get("transactionStatus") or result.raw.get("status") or result.failure_code or ""),
        resolved_status=payment.status,
        success=True,
        response=result.raw,
        requested_by=requested_by if getattr(requested_by, "is_authenticated", False) else None,
    )
    return payment


def webhook_event_id(provider: str, payload: dict[str, Any]) -> str:
    for key in ("event_id", "eventId", "val_id", "paymentID", "paymentId", "trxID", "payment_ref_id", "paymentRefId"):
        value = payload.get(key)
        if value:
            status = payload.get("status") or payload.get("transactionStatus") or ""
            return f"{key}:{value}:{status}"[:180]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(f"{provider}:".encode() + raw).hexdigest()


def process_webhook(*, provider, event_id, payload, handler, payment=None):
    event, created = PaymentWebhookEvent.objects.get_or_create(
        provider=provider,
        event_id=event_id,
        defaults={"payload": payload, "payment": payment},
    )
    if not created:
        return event, False
    try:
        with transaction.atomic():
            handler(payload)
    except Exception as exc:
        event.processing_error = str(exc)
        event.save(update_fields=["processing_error", "updated_at"])
        raise
    event.processed_at = timezone.now()
    if payment and not event.payment_id:
        event.payment = payment
    event.save(update_fields=["processed_at", "payment", "updated_at"])
    return event, True


def find_payment_for_provider_payload(*, provider: str, payload: dict[str, Any]) -> Payment | None:
    if provider == "sslcommerz":
        merchant_reference = str(payload.get("tran_id") or "")
        if merchant_reference:
            return Payment.objects.filter(metadata__merchant_reference=merchant_reference).select_related("order").first()
    elif provider == "bkash":
        reference = str(payload.get("paymentID") or payload.get("paymentId") or "")
        trx_id = str(payload.get("trxID") or "")
        if reference:
            return Payment.objects.filter(gateway_reference=reference).select_related("order").first()
        if trx_id:
            return Payment.objects.filter(transaction_id=trx_id).select_related("order").first()
    elif provider == "nagad":
        reference = str(payload.get("payment_ref_id") or payload.get("paymentRefId") or "")
        order_id = str(payload.get("order_id") or payload.get("orderId") or "")
        if reference:
            return Payment.objects.filter(gateway_reference=reference).select_related("order").first()
        if order_id:
            return Payment.objects.filter(metadata__merchant_reference=order_id).select_related("order").first()
    return None
