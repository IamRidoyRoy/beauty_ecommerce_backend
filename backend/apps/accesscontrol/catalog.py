MODULES = [
    # Catalog
    {"key":"catalog_products","label":"Products & Variants","group":"Catalog","description":"Products list, product create/edit, variants and bulk product Excel."},
    {"key":"catalog_categories","label":"Categories","group":"Catalog","description":"Category list and category management."},
    {"key":"catalog_brands","label":"Brands","group":"Catalog","description":"Brand list and brand management."},
    {"key":"catalog_attributes","label":"Attributes & Taxonomy","group":"Catalog","description":"Attributes, values, skin/hair types, concerns, ingredients and claims."},
    {"key":"catalog_shades","label":"Shades","group":"Catalog","description":"Shade/swatch management."},
    {"key":"catalog_images","label":"Product Images","group":"Catalog","description":"Standalone product and variant image management."},

    # Inventory
    {"key":"inventory_stock","label":"Stock","group":"Inventory","description":"Inventory stock balances and thresholds."},
    {"key":"inventory_warehouses","label":"Warehouses","group":"Inventory","description":"Warehouse list and warehouse management."},
    {"key":"inventory_movements","label":"Stock Movements","group":"Inventory","description":"Inventory movement/audit history."},
    {"key":"inventory_adjustments","label":"Stock Adjustments","group":"Inventory","description":"Increase, decrease or set stock manually."},
    {"key":"inventory_transfers","label":"Stock Transfers","group":"Inventory","description":"Transfer stock between warehouses."},

    # Procurement
    {"key":"procurement_purchases","label":"Purchases","group":"Procurement","description":"Purchase orders, receiving and purchase details."},
    {"key":"procurement_suppliers","label":"Suppliers","group":"Procurement","description":"Supplier list and supplier management."},

    # Sales
    {"key":"orders_view","label":"Orders","group":"Sales","description":"Order list, order details and invoices."},
    {"key":"orders_write","label":"Create & Update Orders","group":"Sales","description":"Create orders and perform order write/status actions allowed by the assigned role.","requires":["orders_view"]},
    {"key":"payments","label":"Payments","group":"Sales","description":"Payment transactions and reconciliation."},

    # Courier
    {"key":"courier_orders","label":"Courier Orders","group":"Courier","description":"Select Packed orders and submit them to a courier."},
    {"key":"courier_shipments","label":"Shipment Tracking","group":"Courier","description":"Track, sync, cancel/return and audit submitted shipments."},
    {"key":"courier_delivery_areas","label":"Delivery Areas","group":"Courier","description":"Delivery modules, districts and thana pricing/overrides."},

    # CRM
    {"key":"customers","label":"Customers","group":"CRM","description":"Customer list and customer details."},

    # Marketing — intentionally split page-by-page.
    {"key":"marketing_coupons","label":"Coupons","group":"Marketing","description":"Coupon codes, limits, restrictions and free-shipping coupons."},
    {"key":"marketing_promotions","label":"Promotions","group":"Marketing","description":"Automatic promotion rules, BOGO, flash sale and targeted promotions."},
    {"key":"marketing_campaigns","label":"Campaigns","group":"Marketing","description":"Scheduled storefront/app campaigns."},
    {"key":"marketing_homepage","label":"Homepage Content","group":"Marketing","description":"Top promotional ticker, hero slider, promo banners and editorial homepage content."},

    # After sales
    {"key":"reviews","label":"Reviews","group":"After Sales","description":"Product review moderation."},
    {"key":"returns","label":"Returns","group":"After Sales","description":"Return request operations."},
    {"key":"refunds","label":"Refunds","group":"After Sales","description":"Refund operations."},

    # Analytics
    {"key":"reports","label":"Reports","group":"Analytics","description":"Sales, product, inventory, customer, profit and operational reports."},

    # Administration / Settings
    {"key":"staff","label":"Users & Roles","group":"Administration","description":"Create staff users and assign detailed module access."},
    {"key":"settings_general","label":"General Settings","group":"Settings","description":"Checkout and general operational settings."},
    {"key":"settings_branding","label":"Branding & Theme","group":"Settings","description":"Website/dashboard logos, names and theme colors."},
    {"key":"settings_payment_gateways","label":"Payment Gateways","group":"Settings","description":"Configure SSLCOMMERZ, bKash and Nagad."},
    {"key":"settings_courier_integrations","label":"Courier Integrations","group":"Settings","description":"Configure Pathao, Steadfast, RedX and CarryBee."},
    {"key":"settings_pixel_tracking","label":"Pixel & Tracking","group":"Settings","description":"GTM, Meta Pixel and Meta Conversions API configuration."},
]

ALL_MODULE_KEYS = tuple(item["key"] for item in MODULES)

# Existing installations may already contain the old broad keys in the JSON access
# profile.  They are expanded in services.py so no database migration is required.
LEGACY_MODULE_EXPANSION = {
    "catalog": ["catalog_products","catalog_categories","catalog_brands","catalog_attributes","catalog_shades","catalog_images"],
    "inventory": ["inventory_stock","inventory_warehouses","inventory_movements","inventory_adjustments","inventory_transfers"],
    "procurement": ["procurement_purchases","procurement_suppliers"],
    "orders": ["orders_view"],
    "order_write": ["orders_view","orders_write"],
    "shipping": ["courier_orders","courier_shipments","courier_delivery_areas"],
    "marketing": ["marketing_coupons","marketing_promotions","marketing_campaigns","marketing_homepage","settings_pixel_tracking"],
    "settings": ["settings_general","settings_branding"],
    "payment_gateways": ["settings_payment_gateways"],
    "courier_gateways": ["settings_courier_integrations"],
}

ROLE_ALLOWED = {
    "super_admin": list(ALL_MODULE_KEYS),
    "admin": list(ALL_MODULE_KEYS),
    "manager": [k for k in ALL_MODULE_KEYS if k not in {"staff", "settings_payment_gateways"}],
    "product_manager": [
        "catalog_products","catalog_categories","catalog_brands","catalog_attributes","catalog_shades","catalog_images","reports"
    ],
    "inventory_manager": [
        "inventory_stock","inventory_warehouses","inventory_movements","inventory_adjustments","inventory_transfers",
        "procurement_purchases","procurement_suppliers","reports"
    ],
    "order_manager": ["orders_view","orders_write","courier_orders","courier_shipments","courier_delivery_areas","returns","reports"],
    "customer_support": ["orders_view","customers","returns","reviews"],
    "marketing_manager": ["marketing_coupons","marketing_promotions","marketing_campaigns","marketing_homepage","settings_pixel_tracking","reports"],
    "finance_manager": ["payments","refunds","reports"],
    "customer": [],
}
ROLE_DEFAULTS = {role:list(values) for role, values in ROLE_ALLOWED.items()}
