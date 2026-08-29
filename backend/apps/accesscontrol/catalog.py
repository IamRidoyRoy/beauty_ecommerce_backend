MODULES = [
    {"key":"catalog","label":"Catalog","group":"Catalog","description":"Products, variants, categories, brands, attributes and product images."},
    {"key":"inventory","label":"Inventory","group":"Inventory","description":"Stock, warehouses, movements, adjustments and transfers."},
    {"key":"procurement","label":"Procurement","group":"Inventory","description":"Purchases and suppliers."},
    {"key":"orders","label":"Orders","group":"Sales","description":"View orders, order details and invoices."},
    {"key":"order_write","label":"Create & update orders","group":"Sales","description":"Create orders and perform write actions allowed by the assigned role."},
    {"key":"payments","label":"Payments","group":"Sales","description":"Payment transaction list and reconciliation."},
    {"key":"shipping","label":"Courier & shipments","group":"Sales","description":"Courier submission, shipment tracking and delivery areas."},
    {"key":"customers","label":"Customers","group":"CRM","description":"Customer list and customer details."},
    {"key":"marketing","label":"Marketing & website content","group":"Marketing","description":"Coupons, promotions, campaigns, homepage content, hero slider and Pixel & Tracking."},
    {"key":"reviews","label":"Reviews","group":"After Sales","description":"Product review moderation."},
    {"key":"returns","label":"Returns","group":"After Sales","description":"Return request operations."},
    {"key":"refunds","label":"Refunds","group":"After Sales","description":"Refund operations."},
    {"key":"reports","label":"Reports","group":"Analytics","description":"Sales, product, customer, profit and operational reports."},
    {"key":"staff","label":"Users & Roles","group":"Administration","description":"Create staff users and assign role/module access."},
    {"key":"settings","label":"General Settings & Branding","group":"Administration","description":"Checkout settings and website/dashboard branding."},
    {"key":"payment_gateways","label":"Payment Gateway Settings","group":"Administration","description":"Configure SSLCOMMERZ, bKash and Nagad."},
    {"key":"courier_gateways","label":"Courier Integration Settings","group":"Administration","description":"Configure Pathao, Steadfast, RedX and CarryBee."},
]

ALL_MODULE_KEYS = tuple(item["key"] for item in MODULES)

ROLE_ALLOWED = {
    "super_admin": list(ALL_MODULE_KEYS),
    "admin": list(ALL_MODULE_KEYS),
    "manager": [k for k in ALL_MODULE_KEYS if k not in {"staff", "payment_gateways"}],
    "product_manager": ["catalog", "reports"],
    "inventory_manager": ["inventory", "procurement", "reports"],
    "order_manager": ["orders", "order_write", "shipping", "returns", "reports"],
    "customer_support": ["orders", "customers", "returns", "reviews"],
    "marketing_manager": ["marketing", "reports"],
    "finance_manager": ["payments", "refunds", "reports"],
    "customer": [],
}
ROLE_DEFAULTS = {role:list(values) for role, values in ROLE_ALLOWED.items()}
