# Courier Integrations response-shape fix

`AdminCourierConfigViewSet` now uses `pagination_class = None` because courier providers are a small fixed configuration registry. The dashboard also normalizes response shapes defensively. No database migration is required.
