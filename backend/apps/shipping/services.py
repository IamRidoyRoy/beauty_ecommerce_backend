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


def _sync_order_from_shipment(shipment: Shipment) -> bool:
    """Advance the commerce order from the courier shipment state.

    The courier status remains the source of truth for fulfilment progress. This
    method is intentionally idempotent: repeated webhook/tracking events never
    move an order backwards and a Delivered shipment can safely be reconciled
    again until the order transition (inventory/payment side effects included)
    succeeds.
    """
    target = None
    if shipment.status in {Shipment.Status.PICKED, Shipment.Status.IN_TRANSIT}:
        target = Order.Status.SHIPPED
    elif shipment.status == Shipment.Status.OUT_FOR_DELIVERY:
        target = Order.Status.OUT_FOR_DELIVERY
    elif shipment.status == Shipment.Status.DELIVERED:
        target = Order.Status.DELIVERED
    if not target:
        return True

    # Always reload the order: webhook and Celery workers can update the same
    # order concurrently and the Shipment relation may hold a stale instance.
    order = Order.objects.filter(pk=shipment.order_id).first()
    if not order:
        return False

    # Return/refund/cancel workflows are terminal business workflows and must
    # never be overwritten by a late courier callback.
    if order.order_status not in ORDER_LIFECYCLE or target not in ORDER_LIFECYCLE:
        return True
    if ORDER_LIFECYCLE.index(target) <= ORDER_LIFECYCLE.index(order.order_status):
        return True

    try:
        transition_order_to_status(order=order, new_status=target, actor=None)
        return True
    except Exception as exc:
        # Do not roll back a valid provider status. A separate local
        # reconciliation task retries Delivered -> Order Delivered every minute
        # without hitting the courier API again. Keep a durable event for ops.
        _record_event(
            provider=shipment.courier,
            action=CourierEvent.Action.TRACK,
            success=False,
            shipment=shipment,
            request_payload={"source": "order_status_sync", "target_order_status": target},
            error=f"Order status sync failed: {exc}",
        )
        return False


def _validate_booking_order(order: Order) -> None:
    # Courier submission is intentionally a Packed -> Shipped workflow. Orders
    # that are already Shipped stay visible in the courier panel but cannot be
    # submitted again, preventing duplicate parcels across providers.
    if order.order_status != Order.Status.PACKED:
        raise CourierGatewayError(
            f"Only Packed orders can be submitted to a courier. {order.order_number} is currently {order.order_status}.",
            code="order_not_packed",
        )
    latest_payment = order.payments.order_by("-created_at").first()
    if latest_payment and latest_payment.method != "cod" and order.payment_status != Order.PaymentStatus.PAID:
        raise CourierGatewayError("Online payment must be verified before courier booking.", code="payment_not_paid")


def _mark_order_shipped_after_booking(order: Order) -> None:
    """Mark a Packed order Shipped only after the courier accepted the parcel.

    Packed -> Shipped has no inventory consumption side effect, so this small
    update is kept inside the courier booking transaction and avoids triggering
    a second auto-book task from the generic order lifecycle service.
    """
    now = timezone.now()
    Order.objects.filter(pk=order.pk, order_status=Order.Status.PACKED).update(
        order_status=Order.Status.SHIPPED,
        fulfillment_status=Order.FulfillmentStatus.PROCESSING,
        updated_at=now,
    )


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
        _mark_order_shipped_after_booking(order)
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


def auto_book_packed_orders(limit: int = 50) -> dict[str, int]:
    """Automatically submit Packed orders when auto-book is enabled."""
    configs = list(CourierConfig.objects.filter(is_active=True, auto_book_enabled=True).order_by("sort_order", "id"))
    if not configs:
        return {"booked": 0, "failed": 0, "skipped": 0}
    booked = failed = skipped = 0
    for cfg in configs:
        qs = Order.objects.filter(order_status=Order.Status.PACKED).exclude(
            shipments__status__in=[Shipment.Status.PENDING, Shipment.Status.BOOKED, Shipment.Status.PICKED, Shipment.Status.IN_TRANSIT, Shipment.Status.OUT_FOR_DELIVERY]
        ).distinct().order_by("created_at")[:limit]
        for order in qs:
            try:
                book_order(order=order, provider=cfg.provider, actor=None, source=Shipment.BookingSource.AUTO)
                booked += 1
            except CourierGatewayError as exc:
                if exc.code in {"payment_not_paid", "shipment_already_exists", "order_not_packed"}:
                    skipped += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
    return {"booked": booked, "failed": failed, "skipped": skipped}


def auto_book_order(order_id: int) -> dict[str, Any]:
    """Auto-book one Packed order with the highest-priority enabled courier."""
    order = Order.objects.filter(pk=order_id).first()
    if not order:
        return {"booked": False, "reason": "order_not_found"}
    if order.order_status != Order.Status.PACKED:
        return {"booked": False, "reason": "order_not_packed"}
    if order.shipments.exclude(
        status__in=[Shipment.Status.CANCELLED, Shipment.Status.FAILED, Shipment.Status.RETURNED]
    ).exists():
        return {"booked": False, "reason": "active_shipment_exists"}

    configs = CourierConfig.objects.filter(is_active=True, auto_book_enabled=True).order_by("sort_order", "id")
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
            if exc.code in {"payment_not_paid", "order_not_packed", "shipment_already_exists"}:
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


def reconcile_delivered_order_statuses(limit: int = 500) -> dict[str, int]:
    """Retry local order completion for courier-confirmed deliveries.

    This is deliberately local-only (no provider API call), so it can run every
    minute cheaply. It closes the reliability gap where a webhook/track request
    stored Shipment=Delivered but an inventory/payment side effect temporarily
    prevented Order=Delivered.
    """
    lifecycle_before_delivered = [
        Order.Status.PENDING,
        Order.Status.CONFIRMED,
        Order.Status.PROCESSING,
        Order.Status.PACKED,
        Order.Status.SHIPPED,
        Order.Status.OUT_FOR_DELIVERY,
    ]
    qs = (
        Shipment.objects.filter(status=Shipment.Status.DELIVERED, order__order_status__in=lifecycle_before_delivered)
        .select_related("order")
        .order_by("delivered_at", "updated_at")[:limit]
    )
    reconciled = failed = 0
    for shipment in qs:
        if _sync_order_from_shipment(shipment):
            reconciled += 1
        else:
            failed += 1
    return {"reconciled": reconciled, "failed": failed}


def _webhook_delivered_result(provider: str, payload: dict[str, Any], shipment: Shipment) -> CourierResult | None:
    """Extract only a *delivered* signal from a verified provider webhook.

    We intentionally do not apply generic webhook statuses such as ``success``
    because some providers use those for request acknowledgement rather than
    parcel delivery. Non-delivered progress still uses the provider tracking API.
    """
    nested_data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    nested_parcel = payload.get("parcel") if isinstance(payload.get("parcel"), dict) else {}
    candidates: list[str] = []
    mapper = None

    if provider == CourierConfig.Provider.PATHAO:
        candidates = [
            payload.get("order_status"),
            payload.get("delivery_status"),
            nested_data.get("order_status"),
            nested_data.get("delivery_status"),
        ]
        mapper = PathaoAdapter._map_status
    elif provider == CourierConfig.Provider.STEADFAST:
        # Steadfast's published webhook body uses ``status`` for parcel status.
        candidates = [payload.get("delivery_status"), payload.get("status"), nested_data.get("delivery_status"), nested_data.get("status")]
        mapper = SteadfastAdapter._map_status
    elif provider == CourierConfig.Provider.REDX:
        candidates = [payload.get("delivery_status"), payload.get("parcel_status"), nested_parcel.get("status"), nested_data.get("parcel_status")]
        mapper = RedXAdapter._map_status
    elif provider == CourierConfig.Provider.CARRYBEE:
        candidates = [payload.get("event"), payload.get("delivery_status"), nested_data.get("status")]
        mapper = CarryBeeAdapter._map_status

    if not mapper:
        return None
    for raw_status in candidates:
        if raw_status in (None, ""):
            continue
        provider_status = str(raw_status)
        if mapper(provider_status) == Shipment.Status.DELIVERED:
            return CourierResult(
                external_id=shipment.external_id,
                tracking_code=shipment.tracking_code,
                provider_status=provider_status,
                status=Shipment.Status.DELIVERED,
                message=provider_status,
                raw={"webhook": payload},
            )
    return None


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
            # A verified webhook that explicitly confirms Delivered updates the
            # local shipment/order immediately. Other progress states still call
            # the provider tracking endpoint so the API remains the reconciliation
            # source of truth. This gives fast delivery completion with a safe
            # periodic fallback if a webhook is missed.
            delivered_result = _webhook_delivered_result(provider, payload, shipment)
            if delivered_result is not None:
                delivered_result.external_id = delivered_result.external_id or tracking
                delivered_result.tracking_code = delivered_result.tracking_code or tracking
                _apply_result(shipment, delivered_result)
            elif provider == CourierConfig.Provider.CARRYBEE and payload.get("event"):
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
