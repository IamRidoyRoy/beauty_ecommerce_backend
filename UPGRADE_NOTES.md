# Backend Dashboard Compatibility Upgrade

Changes in this build:

- Adds `POST /api/v1/admin/products/import-file/` for `.csv` and `.xlsx` product imports.
- Keeps simple/variable product invariants during import.
- Coupon performance and dead-stock reports respect the requested report date range.
- Existing media/order/report APIs remain compatible with the management dashboard.

`openpyxl` is already included in `backend/requirements.txt` for XLSX parsing/export.

No database migration is required for these changes.
