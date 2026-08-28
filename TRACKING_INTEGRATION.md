# Tracking Integration Reference

## Public API

- `GET /api/v1/tracking/config/` — safe public GTM/Pixel configuration and event switches.
- `POST /api/v1/tracking/events/` — first-party event ingest; Django forwards enabled events to Meta Conversions API.

## BEAUTYOPS API

- `GET /api/v1/admin/tracking/settings/`
- `PATCH /api/v1/admin/tracking/settings/`
- `POST /api/v1/admin/tracking/test/`
- `GET /api/v1/admin/tracking/events/`

Only authorized admin/manager/marketing-manager roles can manage these endpoints.

## Purchase deduplication

Django checkout sends the server-side Purchase with:

`event_id = purchase:<order_number>`

The storefront GTM dataLayer uses the same ID for the browser Pixel Purchase. This prevents one order from being counted as two independent conversions when Meta successfully receives both channels.

## Operational behavior

- Master tracking, browser tracking, server tracking, individual events and consent requirement can be changed without redeploying the storefront.
- CAPI token is stored encrypted.
- Server delivery attempts are logged for troubleshooting.
- Marketing tracking is intentionally non-blocking for checkout.
