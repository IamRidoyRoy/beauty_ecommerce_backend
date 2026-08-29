# Granular Staff Dashboard Access

Staff access is now page/module-level instead of broad app-level access.

Examples:
- Marketing: Coupons, Promotions, Campaigns, Homepage Content are independent.
- Catalog: Products, Categories, Brands, Attributes, Shades, Product Images are independent.
- Inventory: Stock, Warehouses, Movements, Adjustments, Transfers are independent.
- Courier: Courier Orders, Shipment Tracking, Delivery Areas are independent.
- Settings: General, Branding, Payment Gateways, Courier Integrations, Pixel & Tracking are independent.

The dashboard hides unauthorized routes and the DRF admin API enforces the same permission keys. Shared read-only lookup APIs are allowed where another permitted page requires them (for example a Coupon editor can read product/brand/category choices without gaining access to Catalog pages).

No database migration is required. Existing `StaffDashboardAccess.modules` rows using legacy broad keys such as `marketing`, `catalog`, `inventory` and `shipping` are expanded automatically at read time. The next time that staff user's access is saved, the new granular keys are persisted.

After changing a staff user's access, have the user sign out and sign in again so the authenticated user payload contains the newest `dashboard_modules` list.
