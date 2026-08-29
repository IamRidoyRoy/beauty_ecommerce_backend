# Dashboard Content & Granular Staff Access

## Content controls

- Marketing -> Homepage Content -> Top promotional bar
- Marketing -> Homepage Content -> Homepage hero slider
- Marketing -> Homepage Content -> promotional/editorial banners

## Staff access

Users & Roles now supports detailed page-level permissions instead of only broad app permissions.

Examples:
- Marketing -> Coupons
- Marketing -> Promotions
- Marketing -> Campaigns
- Marketing -> Homepage Content
- Courier -> Courier Orders / Shipment Tracking / Delivery Areas
- Catalog -> Products / Categories / Brands / Attributes / Shades / Product Images
- Settings -> General / Branding / Payment Gateways / Courier Integrations / Pixel & Tracking

The assigned role remains the capability ceiling. The selected module list can only restrict what that role is already permitted to do.

Backend management API requests use the same granular permission keys, so hiding a sidebar item is not the only protection. Some read-only lookup endpoints intentionally accept related permissions where a permitted page needs reference data (for example coupon targeting needs product/brand/category choices).

## Database migration

For the original content/access upgrade run:

```bash
python manage.py migrate siteconfig
python manage.py migrate accesscontrol
python manage.py migrate
```

Expected migrations include:
- `siteconfig.0003_announcement_item`
- `accesscontrol.0001_initial`

The granular permission expansion itself requires **no new migration**. Existing access rows that contain old broad keys are expanded automatically for backwards compatibility.

After changing a staff user's access, have the user sign out and sign in again so the newest `dashboard_modules` list is loaded.

## Hero image guidance

- Desktop hero: 1600 x 600 px, WebP, <= 200 KB recommended
- Mobile hero: 800 x 1000 px, WebP, <= 200 KB recommended
