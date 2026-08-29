import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.catalog.models import Product, ProductVariant
from .crypto import decrypt_secret
from .models import TrackingEventLog, TrackingSettings


STANDARD_EVENTS = {
    "PageView",
    "ViewContent",
    "Search",
    "AddToCart",
    "AddToWishlist",
    "InitiateCheckout",
    "Purchase",
}

LEGACY_EVENT_MAP = {
    "page_view": "PageView",
    "product_view": "ViewContent",
    "search": "Search",
    "add_to_cart": "AddToCart",
    "wishlist": "AddToWishlist",
    "checkout_started": "InitiateCheckout",
    "buy_now": "InitiateCheckout",
    "order_completed": "Purchase",
}


def normalize_event_name(value: str) -> str:
    value = (value or "").strip()
    if value in STANDARD_EVENTS:
        return value
    return LEGACY_EVENT_MAP.get(value.lower(), value)


def new_event_id(prefix: str = "evt") -> str:
    return f"{prefix}:{uuid.uuid4().hex}"


def _hash(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _normalize_phone(value: Any) -> str:
    raw = "".join(ch for ch in str(value or "") if ch.isdigit())
    if raw.startswith("880"):
        return raw
    if raw.startswith("0") and len(raw) >= 10:
        return f"88{raw}"
    return raw


def request_ip(request) -> str:
    # In production, keep X-Forwarded-For trustworthy by accepting it only from
    # your reverse proxy/load balancer. REMOTE_ADDR remains the fallback.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def build_user_data(*, request=None, user=None, email="", phone="", fbp="", fbc="") -> dict[str, Any]:
    user = user or (getattr(request, "user", None) if request is not None else None)
    email_value = email or getattr(user, "email", "") or ""
    phone_value = phone or getattr(user, "phone", "") or ""
    external_id = getattr(user, "id", None)

    data: dict[str, Any] = {}
    email_hash = _hash(email_value)
    phone_hash = _hash(_normalize_phone(phone_value))
    external_hash = _hash(external_id)
    if email_hash:
        data["em"] = [email_hash]
    if phone_hash:
        data["ph"] = [phone_hash]
    if external_hash:
        data["external_id"] = [external_hash]
    if request is not None:
        ip = request_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")
        if ip:
            data["client_ip_address"] = ip
        if ua:
            data["client_user_agent"] = ua
    if fbp:
        data["fbp"] = fbp
    if fbc:
        data["fbc"] = fbc
    return data


def product_custom_data(*, product_id: int | None, variant_id: int | None = None, quantity: int = 1, currency: str = "BDT") -> dict[str, Any]:
    if not product_id:
        return {}
    product = Product.objects.select_related("brand", "category").filter(pk=product_id).first()
    if not product:
        return {}
    variant = None
    if variant_id:
        variant = ProductVariant.objects.filter(pk=variant_id, product_id=product.id).first()
    price = variant.selling_price if variant is not None else product.base_price
    sku = variant.sku if variant is not None else (product.sku or str(product.id))
    qty = max(1, int(quantity or 1))
    value = Decimal(price or 0) * qty
    return {
        "currency": currency,
        "value": float(value),
        "content_ids": [sku],
        "content_name": product.name,
        "content_type": "product",
        "contents": [{"id": sku, "quantity": qty, "item_price": float(price or 0)}],
    }


def order_custom_data(order, currency: str = "BDT") -> dict[str, Any]:
    contents = []
    content_ids = []
    for item in order.items.all():
        sku = item.sku_snapshot or str(item.product_id or item.id)
        content_ids.append(sku)
        unit_price = Decimal(item.unit_price or 0)
        contents.append({"id": sku, "quantity": item.quantity, "item_price": float(unit_price)})
    return {
        "currency": currency,
        "value": float(order.total or 0),
        "order_id": order.order_number,
        "content_type": "product",
        "content_ids": content_ids,
        "contents": contents,
        "num_items": sum(row["quantity"] for row in contents),
    }


def _safe_response_json(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"data": parsed}
    except Exception:
        return {"raw": raw[:1500]}


def send_meta_event(
    *,
    event_name: str,
    event_id: str,
    event_source_url: str,
    custom_data: dict[str, Any] | None = None,
    user_data: dict[str, Any] | None = None,
    request=None,
    user=None,
    fbp: str = "",
    fbc: str = "",
    email: str = "",
    phone: str = "",
    order_number: str = "",
    test_event: bool = False,
    event_time: int | None = None,
) -> dict[str, Any]:
    settings = TrackingSettings.current()
    event_name = normalize_event_name(event_name)
    custom_data = custom_data or {}
    user_id_ref = getattr(user, "id", None) or getattr(getattr(request, "user", None), "id", None)

    def log(status, *, http_status=None, response_data=None, error_message=""):
        TrackingEventLog.objects.create(
            event_name=event_name,
            event_id=event_id,
            source="server",
            status=status,
            user_id_ref=user_id_ref,
            order_number=order_number,
            http_status=http_status,
            custom_data=custom_data,
            response_data=response_data or {},
            error_message=error_message[:2000],
        )

    if not settings.enabled or not settings.server_tracking_enabled:
        log(TrackingEventLog.Status.SKIPPED, error_message="Server tracking is disabled.")
        return {"sent": False, "reason": "disabled"}
    if not settings.event_enabled(event_name):
        log(TrackingEventLog.Status.SKIPPED, error_message=f"{event_name} is disabled.")
        return {"sent": False, "reason": "event_disabled"}
    pixel_id = settings.meta_pixel_id.strip()
    token = decrypt_secret(settings.meta_access_token_encrypted)
    if not pixel_id or not token:
        log(TrackingEventLog.Status.SKIPPED, error_message="Meta Pixel ID or Conversions API token is missing.")
        return {"sent": False, "reason": "not_configured"}

    payload_event = {
        "event_name": event_name,
        "event_time": event_time or int(time.time()),
        "event_id": event_id,
        "event_source_url": event_source_url or "",
        "action_source": "website",
        "user_data": user_data or build_user_data(
            request=request,
            user=user,
            email=email,
            phone=phone,
            fbp=fbp,
            fbc=fbc,
        ),
        "custom_data": custom_data,
    }
    body: dict[str, Any] = {"data": [payload_event]}
    if (test_event or settings.meta_test_event_code) and settings.meta_test_event_code:
        body["test_event_code"] = settings.meta_test_event_code

    api_version = settings.meta_api_version.strip() or "v26.0"
    endpoint = f"https://graph.facebook.com/{api_version}/{urllib.parse.quote(pixel_id)}/events?access_token={urllib.parse.quote(token)}"
    request_obj = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request_obj, timeout=7) as response:
            raw = response.read().decode("utf-8", errors="replace")
            result = _safe_response_json(raw)
            log(TrackingEventLog.Status.SENT, http_status=response.status, response_data=result)
            return {"sent": True, "status": response.status, "response": result}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        result = _safe_response_json(raw)
        message = result.get("error", {}).get("message") if isinstance(result.get("error"), dict) else raw
        log(TrackingEventLog.Status.FAILED, http_status=exc.code, response_data=result, error_message=str(message or "Meta CAPI request failed."))
        return {"sent": False, "status": exc.code, "response": result, "error": str(message or "Meta CAPI request failed.")}
    except Exception as exc:
        log(TrackingEventLog.Status.FAILED, error_message=str(exc))
        return {"sent": False, "error": str(exc)}


def send_purchase_for_order(*, order, request=None, attribution: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = TrackingSettings.current()
    event_id = f"purchase:{order.order_number}"
    attribution = attribution or {}
    source_url = str(attribution.get("event_source_url") or "")
    fbp = str(attribution.get("fbp") or "")
    fbc = str(attribution.get("fbc") or "")
    if request is not None:
        source_url = request.data.get("event_source_url", "") or request.META.get("HTTP_REFERER", "")
        fbp = request.data.get("fbp", "") or fbp
        fbc = request.data.get("fbc", "") or fbc
    return send_meta_event(
        event_name="Purchase",
        event_id=event_id,
        event_source_url=source_url,
        custom_data=order_custom_data(order, settings.currency),
        request=request,
        user=order.user,
        email=getattr(order.user, "email", "") or "",
        phone=order.customer_phone,
        fbp=fbp,
        fbc=fbc,
        order_number=order.order_number,
    )
