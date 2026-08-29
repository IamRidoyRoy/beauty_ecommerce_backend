# Bulk Product Excel Import / Export

## Dashboard
Catalog > Products now includes:
- Bulk Upload
- Export All
- Download Excel Template
- A stronger Create Product CTA

## API
- `GET /api/v1/admin/products/import-template/` - downloads an XLSX template.
- `POST /api/v1/admin/products/import-file/` - imports `.xlsx` or `.csv`.
- `GET /api/v1/admin/products/export-file/` - downloads all catalog product data.

## Import behavior
- Products are upserted by `product_id`, then simple-product `sku`, then `slug`.
- Variable products can be accompanied by a `Variants` sheet.
- Variants are upserted by `variant_id` or SKU.
- Variant attributes use `Attribute=Value | Attribute=Value`.
- Brand/category/attribute values must already exist.
- Variable products requested as Active are activated only after at least one active variant exists.
- Row failures do not stop other rows; errors are returned with sheet and row number.
- Images are intentionally not imported from Excel.

## Export workbook sheets
- Products
- Variants
- Images
- Beauty Profiles
- Product Claims

No database migration is required for this feature.
