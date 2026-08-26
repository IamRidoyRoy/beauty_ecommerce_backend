# Today Sales / Revenue Fix

- Report date-only filters (`YYYY-MM-DD`) are interpreted in Django's configured business timezone (`Asia/Dhaka`).
- `days=1` now means the current local calendar day from 00:00, not a rolling 24-hour window.
- Sales grouping truncates `created_at` using the current Django timezone explicitly.
- Pending/confirmed/processing/shipped/delivered orders continue to count immediately.
- Cancelled/partially-returned/returned/refunded orders remain excluded from commercial reports.
