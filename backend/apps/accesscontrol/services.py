from .catalog import ALL_MODULE_KEYS, MODULES, ROLE_ALLOWED, ROLE_DEFAULTS
from .models import StaffDashboardAccess


def _allowed_for_role(role):
    return list(ROLE_ALLOWED.get(str(role or ""), []))


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
    selected = ROLE_DEFAULTS.get(str(getattr(user, "role", "")), []) if profile is None else (profile.modules or [])
    return [key for key in ALL_MODULE_KEYS if key in allowed and key in set(selected)]


def is_access_customized(user):
    return get_access_profile(user) is not None


def set_user_modules(user, modules):
    allowed = set(_allowed_for_role(getattr(user, "role", "")))
    requested = [str(x) for x in (modules or [])]
    normalized = [key for key in ALL_MODULE_KEYS if key in allowed and key in set(requested)]
    profile, _ = StaffDashboardAccess.objects.update_or_create(user_id=user.pk, defaults={"modules": normalized})
    user._dashboard_access_profile_cache = profile
    return normalized


def delete_user_access(user_id):
    StaffDashboardAccess.objects.filter(user_id=user_id).delete()


def has_module_access(user, module):
    if not module:
        return True
    if getattr(user, "is_superuser", False):
        return True
    return module in get_effective_modules(user)


def access_options_payload():
    return {
        "modules": MODULES,
        "role_defaults": ROLE_DEFAULTS,
        "role_allowed": ROLE_ALLOWED,
    }


def infer_admin_module(path, method="GET"):
    path = str(path or "")
    if "/api/v1/admin/" not in path:
        return None
    tail = path.split("/api/v1/admin/", 1)[1].lstrip("/")
    if tail.startswith("staff-users") or tail.startswith("staff-access-options"):
        return "staff"
    if tail.startswith("payment-gateways"):
        return "payment_gateways"
    if tail.startswith("courier-configs"):
        return "courier_gateways"
    if tail.startswith("site-settings") or tail.startswith("checkout-settings"):
        return "settings"
    if tail.startswith(("hero-slides", "homepage-banners", "announcement-items", "coupons", "promotions", "tracking/")):
        return "marketing"
    if tail.startswith("inventory/"):
        rest = tail[len("inventory/"):]
        if rest.startswith(("suppliers", "purchases", "purchase-items")):
            return "procurement"
        return "inventory"
    if tail.startswith(("products", "variants", "categories", "brands", "images", "attributes", "attribute-values", "skin-types", "hair-types", "concerns", "ingredients", "claims", "product-claims", "beauty-profiles")):
        return "catalog"
    if tail.startswith("orders"):
        return "orders" if str(method).upper() in {"GET", "HEAD", "OPTIONS"} else "order_write"
    if tail.startswith("customers"):
        return "customers"
    if tail.startswith("payments"):
        return "payments"
    if tail.startswith(("shipping", "shipments", "delivery/")):
        return "shipping"
    if tail.startswith("returns"):
        return "returns"
    if tail.startswith("refunds"):
        return "refunds"
    if tail.startswith("reviews"):
        return "reviews"
    if tail.startswith("reports"):
        return "reports"
    return None
