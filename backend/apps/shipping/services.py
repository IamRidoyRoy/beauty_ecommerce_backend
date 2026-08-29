from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.orders.models import Order
from apps.orders.services import ORDER_LIFECYCLE, transition_order_to_status

from .courier_config import runtime_config, schema_for
from .gateways import CarryBeeAdapter, PathaoAdapter, RedXAdapter, SteadfastAdapter
from .gateways.base import CourierGatewayError, CourierResult
from .models import CourierConfig, CourierEvent, CourierWebhookEvent, Shipment


ADAPTERS = {
    CourierConfig.Provider.PATHAO: PathaoAdapter,
    CourierConfig.Provider.STEADFAST: SteadfastAdapter,
    CourierConfig.Provider.REDX: RedXAdapter,
    CourierConfig.Provider.CARRYBEE: CarryBeeAdapter,
}


def normalize_provider(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "")


def adapter_for(provider: str, *, environment: str | None = None, require_active: bool = True):
    provider = normalize_provider(provider)
    cls = ADAPTERS.get(provider)
    if not cls:
        raise CourierGatewayError(f"Unsupported courier provider: {provider}", code="unsupported_courier")
    runtime = runtime_config(provider, require_active=require_active, environment=environment)
    return cls(runtime)


def _as_gateway_error(exc: Exception, *, provider: str, action: str) -> CourierGatewayError:
    if isinstance(exc, CourierGatewayError):
        return exc
    return CourierGatewayError(
        f"Unexpected {provider.title()} {action} error: {exc}",
        code="courier_unexpected_error",
    )


def _record_event(*, provider: str, action: str, success: bool, shipment=None, request_payload=None, response_payload=None, error="", requested_by=None):
    try:
        CourierEvent.objects.create(
            shipment=shipment,
            provider=provider,
            action=action,
            success=success,
            request_payload=request_payload or {},
            response_payload=response_payload or {},
            error=error or "",
            requested_by=requested_by,
        )
    except Exception:
        pass


def _apply_result(shipment: Shipment, result: CourierResult) -> Shipment:
    now = timezone.now()
    shipment.external_id = result.external_id or shipment.external_id
    shipment.tracking_code = result.tracking_code or shipment.tracking_code
    shipment.provider_status = result.provider_status or shipment.provider_status
    shipment.provider_message = result.message or shipment.provider_message
    shipment.status = result.status or shipment.status
    shipment.last_synced_at = now
    if result.raw:
        shipment.payload = {**(shipment.payload or {}), "last_provider_response": result.raw}
    if shipment.status == Shipment.Status.BOOKED and not shipment.booked_at:
        shipment.booked_at = now
    if shipment.status == Shipment.Status.PICKED and not shipment.picked_up_at:
        shipment.picked_up_at = now
    if shipment.status in {Shipment.Status.IN_TRANSIT, Shipment.Status.OUT_FOR_DELIVERY} and not shipment.dispatched_at:
        shipment.dispatched_at = now
    if shipment.status == Shipment.Status.DELIVERED and not shipment.delivered_at:
        shipment.delivered_at = now
    if shipment.status == Shipment.Status.CANCELLED and not shipment.cancelled_at:
        shipment.cancelled_at = now
    shipment.save()
    _sync_order_from_shipment(shipment)
    return shipment


def _sync_order_from_shipment(shipment: Shipment) -> None:
    target = None
    if shipment.status in {Shipment.Status.PICKED, Shipment.Status.IN_TRANSIT}:
        target = Order.Status.SHIPPED
    elif shipment.status == Shipment.Status.OUT_FOR_DELIVERY:
        target = Order.Status.OUT_FOR_DELIVERY
    elif shipment.status == Shipment.Status.DELIVERED:
        target = Order.Status.DELIVERED
    if not target:
        return
    order = shipment.order
    if order.order_status not in ORDER_LIFECYCLE or target not in ORDER_LIFECYCLE:
        return
    if ORDER_LIFECYCLE.index(target) <= ORDER_LIFECYCLE.index(order.order_status):
        return
    try:
        transition_order_to_status(order=order, new_status=target, actor=None)
    except Exception:
        # Shipment tracking must never be lost because an order workflow side effect failed.
        pass


def _validate_booking_order(order: Order) -> None:
    if order.order_status in {Order.Status.CANCELLED, Order.Status.DELIVERED, Order.Status.RETURNED, Order.Status.REFUNDED}:
        raise CourierGatewayError(f"Order {order.order_number} cannot be booked in status {order.order_status}.", code="order_not_bookable")
    latest_payment = order.payments.order_by("-created_at").first()
    if latest_payment and latest_payment.method != "cod" and order.payment_status != Order.PaymentStatus.PAID:
        raise CourierGatewayError("Online payment must be verified before courier booking.", code="payment_not_paid")


@transaction.atomic
def book_order(*, order: Order, provider: str, options: dict[str, Any] | None = None, actor=None, source: str = Shipment.BookingSource.MANUAL) -> Shipment:
    provider = normalize_provider(provider)
    order = Order.objects.select_for_update().prefetch_related("items", "payments", "shipments").get(pk=order.pk)
    _validate_booking_order(order)
    duplicate = order.shipments.exclude(
        status__in=[Shipment.Status.CANCELLED, Shipment.Status.FAILED, Shipment.Status.RETURNED]
    ).first()
    if duplicate:
        raise CourierGatewayError(
            f"This order already has an active {duplicate.courier.title()} shipment ({duplicate.tracking_code or duplicate.external_id or duplicate.id}).",
            code="shipment_already_exists",
        )
    adapter = adapter_for(provider, require_active=True)
    shipment = Shipment.objects.create(
        order=order,
        courier=provider,
        environment=adapter.runtime.environment,
        status=Shipment.Status.PENDING,
        booking_source=source,
        booked_by=actor,
        payload={"booking_options": options or {}},
    )
    request_payload = {"order": order.order_number, "options": options or {}, "environment": adapter.runtime.environment}
    try:
        result = adapter.create_shipment(order, options=options or {})
        _apply_result(shipment, result)
        _record_event(provider=provider, action=CourierEvent.Action.BOOK, success=True, shipment=shipment, request_payload=request_payload, response_payload=result.raw, requested_by=actor)
        return shipment
    except Exception as exc:
        shipment.status = Shipment.Status.FAILED
        shipment.provider_message = str(exc)
        shipment.last_synced_at = timezone.now()
        shipment.save(update_fields=["status", "provider_message", "last_synced_at", "updated_at"])
        _record_event(provider=provider, action=CourierEvent.Action.BOOK, success=False, shipment=shipment, request_payload=request_payload, error=str(exc), response_payload=getattr(exc, "response", None) or {}, requested_by=actor)
        raise _as_gateway_error(exc, provider=provider, action="booking") from exc


def track_shipment(*, shipment: Shipment, actor=None) -> Shipment:
    provider = normalize_provider(shipment.courier)
    adapter = adapter_for(provider, environment=shipment.environment or None, require_active=False)
    try:
        result = adapter.track(shipment)
        _apply_result(shipment, result)
        _record_event(provider=provider, action=CourierEvent.Action.TRACK, success=True, shipment=shipment, response_payload=result.raw, requested_by=actor)
        return shipment
    except Exception as exc:
        _record_event(provider=provider, action=CourierEvent.Action.TRACK, success=False, shipment=shipment, error=str(exc), response_payload=getattr(exc, "response", None) or {}, requested_by=actor)
        raise _as_gateway_error(exc, provider=provider, action="tracking") from exc


def cancel_shipment(*, shipment: Shipment, reason: str = "", actor=None) -> Shipment:
    provider = normalize_provider(shipment.courier)
    if shipment.status in {Shipment.Status.DELIVERED, Shipment.Status.RETURNED, Shipment.Status.CANCELLED}:
        raise CourierGatewayError(f"Shipment cannot be cancelled in status {shipment.status}.", code="shipment_not_cancellable")
    adapter = adapter_for(provider, environment=shipment.environment or None, require_active=False)
    cfg = CourierConfig.objects.filter(provider=provider).only("cancel_api_enabled").first()
    if not (cfg and cfg.cancel_api_enabled):
        raise CourierGatewayError(
            f"Provider-side cancellation is disabled for {adapter.runtime.display_name}. Enable it only after verifying your merchant API contract and sandbox test.",
            code="cancel_api_disabled",
        )
    if not adapter.supports_cancel:
        raise CourierGatewayError(
            f"{adapter.runtime.display_name} does not expose a verified merchant API cancellation endpoint. Cancel it from the courier merchant panel instead.",
            code="cancel_not_supported",
        )
    try:
        result = adapter.cancel_shipment(shipment, reason=reason)
        _apply_result(shipment, result)
        _record_event(provider=provider, action=CourierEvent.Action.CANCEL, success=True, shipment=shipment, request_payload={"reason": reason}, response_payload=result.raw, requested_by=actor)
        return shipment
    except Exception as exc:
        _record_event(provider=provider, action=CourierEvent.Action.CANCEL, success=False, shipment=shipment, request_payload={"reason": reason}, error=str(exc), response_payload=getattr(exc, "response", None) or {}, requested_by=actor)
        raise _as_gateway_error(exc, provider=provider, action="cancellation") from exc


def request_steadfast_return(*, shipment: Shipment, reason: str = "", actor=None) -> dict[str, Any]:
    if normalize_provider(shipment.courier) != CourierConfig.Provider.STEADFAST:
        raise CourierGatewayError("Return-request API is only available for Steadfast shipments here.", code="unsupported_action")
    adapter = adapter_for(CourierConfig.Provider.STEADFAST, environment=shipment.environment or None, require_active=False)
    try:
        data = adapter.create_return_request(shipment, reason=reason)
        _record_event(provider="steadfast", action=CourierEvent.Action.CANCEL, success=True, shipment=shipment, request_payload={"return_request": True, "reason": reason}, response_payload=data, requested_by=actor)
        return data
    except Exception as exc:
        _record_event(provider="steadfast", action=CourierEvent.Action.CANCEL, success=False, shipment=shipment, request_payload={"return_request": True, "reason": reason}, error=str(exc), response_payload=getattr(exc, "response", None) or {}, requested_by=actor)
        raise _as_gateway_error(exc, provider="steadfast", action="return request") from exc


def test_courier_connection(config: CourierConfig, *, actor=None) -> dict[str, Any]:
    provider = config.provider
    adapter = adapter_for(provider, require_active=False)
    try:
        data = adapter.test_connection()
        _record_event(provider=provider, action=CourierEvent.Action.TEST, success=True, response_payload=data, requested_by=actor)
        return data
    except Exception as exc:
        _record_event(provider=provider, action=CourierEvent.Action.TEST, success=False, error=str(exc), response_payload=getattr(exc, "response", None) or {}, requested_by=actor)
        raise _as_gateway_error(exc, provider=provider, action="connection test") from exc


def _eligible_order_statuses(trigger_status: str) -> tuple[str, ...]:
    """Statuses at/after the configured trigger where booking is still meaningful.

    This catches an order that was advanced multiple lifecycle steps in one dashboard action
    while the async courier task was waiting to run.
    """
    if trigger_status not in ORDER_LIFECYCLE:
        return (trigger_status,)
    start = ORDER_LIFECYCLE.index(trigger_status)
    delivered = ORDER_LIFECYCLE.index(Order.Status.DELIVERED)
    return tuple(ORDER_LIFECYCLE[start:delivered])


def auto_book_ready_orders(limit: int = 50) -> dict[str, int]:
    configs = list(CourierConfig.objects.filter(is_active=True, auto_book_enabled=True).order_by("sort_order", "id"))
    if not configs:
        return {"booked": 0, "failed": 0, "skipped": 0}
    booked = failed = skipped = 0
    for cfg in configs:
        qs = Order.objects.filter(order_status__in=_eligible_order_statuses(cfg.auto_book_order_status)).exclude(
            shipments__status__in=[Shipment.Status.PENDING, Shipment.Status.BOOKED, Shipment.Status.PICKED, Shipment.Status.IN_TRANSIT, Shipment.Status.OUT_FOR_DELIVERY]
        ).distinct().order_by("created_at")[:limit]
        for order in qs:
            try:
                book_order(order=order, provider=cfg.provider, actor=None, source=Shipment.BookingSource.AUTO)
                booked += 1
            except CourierGatewayError as exc:
                if exc.code in {"payment_not_paid", "shipment_already_exists", "order_not_bookable"}:
                    skipped += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
    return {"booked": booked, "failed": failed, "skipped": skipped}


def auto_book_order(order_id: int) -> dict[str, Any]:
    """Auto-book one order with the highest-priority eligible courier.

    This is used by the order lifecycle on-commit hook for near real-time booking.
    The periodic scanner remains as a catch-up path if Celery was temporarily unavailable.
    """
    order = Order.objects.filter(pk=order_id).first()
    if not order:
        return {"booked": False, "reason": "order_not_found"}
    if order.shipments.exclude(
        status__in=[Shipment.Status.CANCELLED, Shipment.Status.FAILED, Shipment.Status.RETURNED]
    ).exists():
        return {"booked": False, "reason": "active_shipment_exists"}

    if order.order_status not in ORDER_LIFECYCLE or order.order_status == Order.Status.DELIVERED:
        return {"booked": False, "reason": "order_status_not_auto_bookable"}
    current_index = ORDER_LIFECYCLE.index(order.order_status)
    configs = [
        cfg
        for cfg in CourierConfig.objects.filter(is_active=True, auto_book_enabled=True).order_by("sort_order", "id")
        if cfg.auto_book_order_status in ORDER_LIFECYCLE
        and ORDER_LIFECYCLE.index(cfg.auto_book_order_status) <= current_index
    ]
    last_error = ""
    for cfg in configs:
        try:
            shipment = book_order(
                order=order,
                provider=cfg.provider,
                actor=None,
                source=Shipment.BookingSource.AUTO,
            )
            return {
                "booked": True,
                "shipment_id": shipment.id,
                "provider": shipment.courier,
                "tracking_code": shipment.tracking_code,
            }
        except CourierGatewayError as exc:
            last_error = f"{exc.code}: {exc}"
            # A validation error tied to the order itself will not be fixed by trying another courier.
            if exc.code in {"payment_not_paid", "order_not_bookable", "shipment_already_exists"}:
                break
        except Exception as exc:
            last_error = str(exc)
    return {"booked": False, "reason": last_error or "no_matching_auto_book_courier"}


def sync_open_shipments(limit: int = 200) -> dict[str, int]:
    qs = Shipment.objects.exclude(status__in=[Shipment.Status.DELIVERED, Shipment.Status.RETURNED, Shipment.Status.CANCELLED]).exclude(tracking_code="").order_by("last_synced_at", "updated_at")[:limit]
    synced = failed = 0
    for shipment in qs:
        try:
            track_shipment(shipment=shipment)
            synced += 1
        except Exception:
            failed += 1
    return {"synced": synced, "failed": failed}


def process_webhook(*, provider: str, payload: dict[str, Any], headers: dict[str, Any]) -> Shipment | None:
    provider = normalize_provider(provider)
    cfg = CourierConfig.objects.filter(provider=provider).first()
    if not cfg:
        raise CourierGatewayError("Courier is not configured.", code="courier_not_configured")
    runtime = runtime_config(provider, require_active=False)
    values = runtime.values
    lower_headers = {str(k).lower(): str(v) for k, v in headers.items()}
    if provider == "pathao":
        secret = str(values.get("webhook_secret") or "").strip()
        if not secret:
            raise CourierGatewayError("Pathao webhook verification secret is not configured.", code="webhook_not_configured")
        supplied = lower_headers.get("x-pathao-merchant-webhook-integration-secret", "").strip()
        if supplied != secret:
            raise CourierGatewayError("Invalid Pathao webhook secret.", code="invalid_webhook_signature")
    elif provider == "steadfast":
        secret = str(values.get("webhook_bearer_token") or "").strip()
        if not secret:
            raise CourierGatewayError("Steadfast webhook bearer token is not configured.", code="webhook_not_configured")
        supplied = lower_headers.get("authorization", "").strip()
        if supplied != f"Bearer {secret}":
            raise CourierGatewayError("Invalid Steadfast webhook bearer token.", code="invalid_webhook_signature")
    elif provider == "redx":
        secret = str(values.get("webhook_token") or "").strip()
        if not secret:
            raise CourierGatewayError("RedX webhook verification token is not configured.", code="webhook_not_configured")
        supplied = lower_headers.get("api-access-token", "").strip()
        supplied_token = supplied[7:].strip() if supplied.lower().startswith("bearer ") else supplied
        if supplied_token != secret:
            raise CourierGatewayError("Invalid RedX webhook token.", code="invalid_webhook_signature")
    elif provider == "carrybee":
        # CarryBee sends X-Carrybee-Webhook-Signature. Accept the configured secret
        # from either environment so a sandbox webhook can still finish while an
        # administrator is switching the default config to Live (and vice versa).
        candidates = set()
        for env in ("sandbox", "live"):
            try:
                env_values = cfg.get_environment_config(env)
            except Exception:
                env_values = {}
            candidate = str(env_values.get("webhook_secret") or "").strip()
            if candidate:
                candidates.add(candidate)
        if not candidates:
            raise CourierGatewayError("CarryBee webhook secret is not configured.", code="webhook_not_configured")
        supplied = lower_headers.get("x-carrybee-webhook-signature", "").strip()
        if not supplied or not any(hmac.compare_digest(supplied, candidate) for candidate in candidates):
            raise CourierGatewayError("Invalid CarryBee webhook signature.", code="invalid_webhook_signature")

    raw = json.dumps(payload, sort_keys=True, default=str)
    event_id = str(payload.get("event_id") or payload.get("id") or hashlib.sha256(raw.encode()).hexdigest())[:180]
    event, created = CourierWebhookEvent.objects.get_or_create(provider=provider, event_id=event_id, defaults={"payload": payload})
    if not created and event.processed_at:
        return event.shipment

    tracking = str(payload.get("tracking_code") or payload.get("tracking_number") or payload.get("tracking_id") or payload.get("consignment_id") or payload.get("consignmentId") or "")
    invoice = str(payload.get("invoice") or payload.get("merchant_order_id") or payload.get("merchant_invoice_id") or "")
    shipment = None
    if tracking:
        shipment = Shipment.objects.filter(courier=provider).filter(tracking_code=tracking).first() or Shipment.objects.filter(courier=provider, external_id=tracking).first()
    if not shipment and invoice:
        shipment = Shipment.objects.filter(courier=provider, order__order_number=invoice).order_by("-created_at").first()
    if shipment:
        try:
            # CarryBee webhooks provide a signed event name. Apply it immediately so
            # customer/admin tracking updates do not depend on a second provider call.
            # The periodic/details API sync remains the reconciliation source of truth.
            if provider == CourierConfig.Provider.CARRYBEE and payload.get("event"):
                provider_event = str(payload.get("event") or "")
                _apply_result(
                    shipment,
                    CourierResult(
                        external_id=shipment.external_id or tracking,
                        tracking_code=shipment.tracking_code or tracking,
                        provider_status=provider_event,
                        status=CarryBeeAdapter._map_status(provider_event),
                        message=str(payload.get("reason") or provider_event),
                        raw={"webhook": payload},
                    ),
                )
            else:
                track_shipment(shipment=shipment)
            event.shipment = shipment
            event.processed_at = timezone.now()
            event.processing_error = ""
        except Exception as exc:
            event.shipment = shipment
            event.processing_error = str(exc)
    else:
        event.processing_error = "No matching shipment found."
    event.save(update_fields=["shipment", "processed_at", "processing_error", "updated_at"])
    _record_event(provider=provider, action=CourierEvent.Action.WEBHOOK, success=bool(shipment and event.processed_at), shipment=shipment, response_payload=payload, error=event.processing_error)
    return shipment
