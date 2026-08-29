# Courier Test Connection POST Fix

## Issue
The dashboard sends `POST /api/v1/admin/courier-configs/<id>/test-connection/`, but `AdminCourierConfigViewSet.http_method_names` did not include `post`. DRF therefore returned HTTP 405 (`Method POST not allowed`) before the provider adapter was called.

## Fix
- Enabled POST on the viewset so detail actions such as `test-connection` can execute.
- Kept collection-level courier configuration creation disabled. Courier providers remain a fixed registry managed by `ensure_courier_configs()`.
- No database migration is required.

## Expected test flow
1. Save sandbox credentials.
2. Keep Sandbox mode enabled.
3. Click Test Connection.
4. Backend authenticates with the selected provider environment and returns the provider response.
5. After a successful connection test, enable Active and Save to expose the courier in Sales > Courier.
