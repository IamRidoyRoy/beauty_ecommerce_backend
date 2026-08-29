from collections.abc import Iterable

from .catalog import (
    ALL_MODULE_KEYS,
    LEGACY_MODULE_EXPANSION,
    MODULES,
    ROLE_ALLOWED,
    ROLE_DEFAULTS,
)
from .models import StaffDashboardAccess


def _allowed_for_role(role):
    return list(ROLE_ALLOWED.get(str(role or ""), []))


def _expand_legacy(values):
    """Expand access values saved by older builds into the current granular keys."""
    expanded = []
    seen = set()
    for raw in values or []:
        key = str(raw)
        targets = LEGACY_MODULE_EXPANSION.get(key, [key])
        for target in targets:
            if target in ALL_MODULE_KEYS and target not in seen:
                expanded.append(target)
                seen.add(target)
    return expanded


def _with_requirements(values):
    selected = set(values or [])
    changed = True
    by_key = {item["key"]: item for item in MODULES}
    while changed:
        changed = False
        for key in tuple(selected):
            for required in by_key.get(key, {}).get("requires", []):
                if required not in selected:
                    selected.add(required)
                    changed = True
    return [key for key in ALL_MODULE_KEYS if key in selected]


def get_access_profile(user):
    if not user or not getattr(user, "pk", None):
        return None
    if hasattr(user, "_dashboard_access_profile_cache"):
        return user._dashboard_access_profile_cache
    profile = StaffDashboardAccess.objects.filter(user_id=user.pk).first()
    user._dashboard_access_profile_cache = profile
    return profile


def get_effective_modules(user):
    if not user or not getattr(user, "is_authenticated", False):
        return []
    if getattr(user, "is_superuser", False):
        return list(ALL_MODULE_KEYS)
    allowed = set(_allowed_for_role(getattr(user, "role", "")))
    profile = get_access_profile(user)
    selected = ROLE_DEFAULTS.get(str(getattr(user, "role", "")), []) if profile is None else _expand_legacy(profile.modules or [])
    selected = _with_requirements(selected)
    return [key for key in ALL_MODULE_KEYS if key in allowed and key in set(selected)]


def is_access_customized(user):
    return get_access_profile(user) is not None


def set_user_modules(user, modules):
    allowed = set(_allowed_for_role(getattr(user, "role", "")))
    requested = _with_requirements(_expand_legacy([str(x) for x in (modules or [])]))
    normalized = [key for key in ALL_MODULE_KEYS if key in allowed and key in set(requested)]
    profile, _ = StaffDashboardAccess.objects.update_or_create(user_id=user.pk, defaults={"modules": normalized})
    user._dashboard_access_profile_cache = profile
    return normalized


def delete_user_access(user_id):
    StaffDashboardAccess.objects.filter(user_id=user_id).delete()


def has_module_access(user, module):
    """Accept a single module or an iterable of acceptable modules (OR semantics)."""
    if not module:
        return True
    if getattr(user, "is_superuser", False):
        return True
    effective = set(get_effective_modules(user))
    if isinstance(module, str):
        return module in effective
    if isinstance(module, Iterable):
        return any(str(item) in effective for item in module)
    return False


def access_options_payload():
    return {
        "modules": MODULES,
        "role_defaults": ROLE_DEFAULTS,
        "role_allowed": ROLE_ALLOWED,
    }


def infer_admin_module(path, method="GET"):
    """Return the detailed dashboard permission(s) required by an admin API path.

    For shared lookup endpoints we return multiple acceptable modules. This lets a
    page use reference data (for example Products in a coupon target selector)
    without giving the staff user access to the separate Products dashboard page.
    """
    path = str(path or "")
    method = str(method or "GET").upper()
    read = method in {"GET", "HEAD", "OPTIONS"}
    if "/api/v1/admin/" not in path:
        return None
    tail = path.split("/api/v1/admin/", 1)[1].lstrip("/")

    if tail.startswith("staff-users") or tail.startswith("staff-access-options"):
        return "staff"
    if tail.startswith("payment-gateways"):
        return "settings_payment_gateways"
    if tail.startswith("courier-configs"):
        return "settings_courier_integrations"
    if tail.startswith("site-settings"):
        return "settings_branding"
    if tail.startswith("checkout-settings"):
        return "settings_general"
    if tail.startswith("tracking/"):
        return "settings_pixel_tracking"
    if tail.startswith(("hero-slides", "homepage-banners", "announcement-items")):
        return "marketing_homepage"
    if tail.startswith("coupons"):
        return "marketing_coupons"
    if tail.startswith("campaigns"):
        return "marketing_campaigns"
    if tail.startswith("promotions"):
        return "marketing_promotions"

    if tail.startswith("inventory/"):
        rest = tail[len("inventory/"):]
        if rest.startswith("suppliers"):
            return "procurement_suppliers"
        if rest.startswith(("purchases", "purchase-items")):
            return "procurement_purchases"
        if rest.startswith("warehouses"):
            return ("inventory_warehouses", "inventory_stock", "inventory_adjustments", "inventory_transfers", "procurement_purchases") if read else "inventory_warehouses"
        if rest.startswith("movements"):
            return "inventory_movements"
        if rest.startswith("adjust"):
            return "inventory_adjustments"
        if rest.startswith("transfer"):
            return "inventory_transfers"
        if rest.startswith("resolve-stock-item"):
            return ("inventory_stock", "inventory_adjustments", "inventory_transfers", "procurement_purchases")
        if "/thresholds/" in rest:
            return "inventory_stock"
        return "inventory_stock"

    if tail.startswith(("products", "variants")):
        if read:
            return (
                "catalog_products", "inventory_stock", "inventory_adjustments", "inventory_transfers",
                "procurement_purchases", "orders_write", "marketing_coupons", "marketing_promotions", "marketing_homepage",
            )
        return "catalog_products"
    if tail.startswith("categories"):
        if read:
            return ("catalog_categories", "catalog_products", "marketing_coupons", "marketing_promotions", "marketing_homepage")
        return "catalog_categories"
    if tail.startswith("brands"):
        if read:
            return ("catalog_brands", "catalog_products", "marketing_coupons", "marketing_promotions", "marketing_homepage")
        return "catalog_brands"
    if tail.startswith("images"):
        return ("catalog_images", "catalog_products")
    if tail.startswith(("attributes", "attribute-values", "skin-types", "hair-types", "concerns", "ingredients", "claims", "product-claims", "beauty-profiles")):
        if read:
            return ("catalog_attributes", "catalog_shades", "catalog_products")
        # Attribute values are also used by the standalone Shades screen.
        if tail.startswith("attribute-values"):
            return ("catalog_attributes", "catalog_shades", "catalog_products")
        return ("catalog_attributes", "catalog_products")

    if tail.startswith("orders"):
        return "orders_view" if read else "orders_write"
    if tail.startswith("customers"):
        return ("customers", "orders_write") if read else "customers"
    if tail.startswith("payments"):
        return "payments"

    if tail.startswith("shipments/courier-orders") or tail.startswith("shipments/submit-orders") or tail.startswith("shipments/available-couriers") or tail.startswith("shipments/book"):
        return "courier_orders"
    if tail.startswith("shipments"):
        return "courier_shipments"
    if tail.startswith("delivery/"):
        return "courier_delivery_areas"
    if tail.startswith("shipping"):
        return "courier_delivery_areas"

    if tail.startswith("returns"):
        return "returns"
    if tail.startswith("refunds"):
        return "refunds"
    if tail.startswith("reviews"):
        return "reviews"
    if tail.startswith("reports"):
        return "reports"
    return None
