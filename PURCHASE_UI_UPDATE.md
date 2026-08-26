# Purchase detail API update

`PurchaseItemSerializer` now exposes read-only display fields:

- `target_name`
- `target_sku`
- `target_image`
- `variant_label`

Purchase querysets prefetch product/variant images and variant attributes to avoid N+1 queries on purchase detail.
No database migration is required.
