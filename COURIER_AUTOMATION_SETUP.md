# Courier Automation — Pathao, Steadfast, RedX & CarryBee

This upgrade makes courier operations dashboard-controlled and keeps courier credentials in the backend database encrypted at rest.

## Included

- Pathao: connection test, parcel booking, tracking sync, webhook verification, sandbox/live configuration.
- Steadfast: connection test, parcel booking, tracking sync, return request, webhook verification. The currently documented merchant API does not expose a direct parcel-cancel endpoint, so the dashboard does not falsely mark a Steadfast parcel as cancelled.
- RedX: connection test, parcel booking, area lookup, tracking sync, sandbox/live configuration, parcel cancellation request, webhook endpoint.
- CarryBee: Developers API v2 connection test, sandbox/live booking, address-to-city/zone resolution, manual location override fallback, tracking sync, cancellation, and webhook updates.
- Per-provider Active / Inactive control.
- Per-provider Auto Book toggle and priority.
- RedX provider-side cancellation is a separate explicit opt-in and is OFF by default.
- Configurable order status that triggers auto booking (default: `ready_to_ship`).
- Near-real-time Celery task after an order transition plus a one-minute catch-up scan.
- Five-minute tracking reconciliation/sync for open shipments.
- Courier event history for booking, tracking, cancellation/return, webhook and connection tests.
- Customer Order Detail API/UI shows courier, tracking code and latest courier status.
- Only Super Admin/Admin can change courier credentials; operational shipment actions retain the existing shipping/order-management permissions.

## Dashboard

Open:

`Settings -> Courier Integrations`

For each provider:

1. Configure credentials.
2. Use **Test Connection**.
3. For Pathao/RedX/CarryBee choose Sandbox or Live.
4. Enable **Active** to make the courier selectable for booking.
5. Enable **Auto book** if orders should be booked automatically.
6. Choose the order status that triggers auto booking and set priority. Lower priority numbers are tried first.

Shipment operations are available at:

`Sales -> Shipments`

The order detail screen also has **Shipment** booking and a courier shipment summary.

## Environment security

Set a stable Fernet key in production:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Then set:

```env
COURIER_CONFIG_ENCRYPTION_KEY=YOUR_GENERATED_FERNET_KEY
COURIER_API_TIMEOUT=20
```

Never commit the production encryption key to Git. If this key is changed after credentials have been saved, the existing encrypted credentials cannot be decrypted until the original key is restored.

## Database migration

This project previously had shipping tables but no committed shipping migrations. For an **existing database** where `shipping_shippingmethod` / `shipping_shipment` already exist, run:

```bash
python manage.py migrate shipping 0001 --fake-initial
python manage.py migrate shipping
python manage.py migrate
```

Do **not** fake `0002_courier_automation` or `0003_carrybee`; they create/update the courier automation schema and seed CarryBee configuration.

Verify:

```bash
python manage.py showmigrations shipping
```

Expected:

```text
shipping
 [X] 0001_initial
 [X] 0002_courier_automation
 [X] 0003_carrybee
```

For a genuinely fresh database with a complete migration baseline, normal `python manage.py migrate` is sufficient.

## Celery / automatic booking and tracking

Both a Celery worker and Celery Beat should be running. From the backend directory:

```bash
celery -A config worker -l info
```

In another process:

```bash
celery -A config beat -l info
```

Scheduled tasks:

- `apps.shipping.tasks.auto_book_courier_orders` — every 60 seconds (catch-up).
- `apps.shipping.tasks.sync_courier_shipments` — every 5 minutes.
- `apps.shipping.tasks.auto_book_courier_order` — queued immediately after an order lifecycle transition; it books only when a configured auto-book rule matches the order's current status.

If the broker/worker is briefly unavailable, the on-commit task is best-effort and the periodic scan is the fallback.

## Webhooks

Webhook endpoints:

```text
POST /api/v1/courier/webhooks/pathao/
POST /api/v1/courier/webhooks/steadfast/
POST /api/v1/courier/webhooks/redx/
POST /api/v1/courier/webhooks/carrybee/
```

Configure the relevant webhook verification secret/token in the Dashboard before enabling a provider webhook. The backend rejects webhook calls when the verification secret is missing or invalid.

Because provider webhook setup and header names can be merchant-contract specific, confirm the exact webhook settings in the provider merchant portal during onboarding.

## Provider configuration fields

### Pathao

Sandbox and Live are stored separately.

- Client ID
- Client Secret
- Merchant Username / Email
- Merchant Password
- Pickup Store ID
- Webhook Integration Secret
- Default Parcel Weight (kg)
- Optional custom base URL

Current default URLs used by the integration:

```text
Sandbox: https://courier-api-sandbox.pathao.com
Live:    https://api-hermes.pathao.com
```

The create-order integration uses Pathao's current auto-address flow and sends the recipient address without requiring the legacy city/zone/area IDs.

### Steadfast

- API Key
- Secret Key
- Webhook Bearer Token
- Optional custom base URL

Default API URL:

```text
https://portal.steadfast.com.bd/api/v1
```

There is no public sandbox toggle in this implementation because the documented merchant API does not provide a separate public sandbox environment. Use credentials/test procedures supplied by Steadfast if your merchant account has a private test environment and set a custom base URL only when they explicitly provide one.

Direct cancellation is not presented as supported. For Steadfast shipments, the dashboard exposes the documented **Return Request** API instead.

### RedX

Sandbox and Live are stored separately.

- API Access Token
- Pickup Store ID
- Webhook Verification Token
- Default Parcel Weight (grams)
- Optional Cancellation / Parcel Update Endpoint (only if your merchant contract provides it)
- Optional custom base URL

Default URLs:

```text
Sandbox: https://sandbox.redx.com.bd/v1.0.0-beta
Live:    https://openapi.redx.com.bd/v1.0.0-beta
```

The backend attempts to resolve the RedX delivery area from the order district/thana. If no reliable match is found, the dashboard lets an operator provide the RedX Delivery Area ID and name manually.

**Cancellation note:** the currently published RedX public OpenAPI describes create/track/info operations, while some merchant/reseller contracts document parcel-update capabilities. For that reason **API cancel is OFF by default**. Enter the exact cancellation/parcel-update endpoint supplied for your merchant account, enable **API cancel** in the dashboard, and validate it in Sandbox before Live. The adapter only marks the local shipment cancelled after the provider PATCH request succeeds.

### CarryBee

Sandbox and Live credentials are stored separately.

- Client ID
- Client Secret
- Client Context
- Pickup Store ID
- Webhook Secret
- Default Delivery Type (`1` Normal, `2` Express)
- Default Product Type (`1` Parcel, `2` Book, `3` Document)
- Default Parcel Weight (grams)
- Optional custom base URL

Default URLs used by the adapter:

```text
Sandbox: https://stage-sandbox.carrybee.com
Live:    https://developers.carrybee.com
```

The adapter uses CarryBee Developers API v2 headers (`Client-ID`, `Client-Secret`, `Client-Context`). It books through `/api/v2/orders`, tracks through the order-details endpoint, and exposes provider cancellation only when **API cancel** is explicitly enabled in the Dashboard.

CarryBee booking requires `city_id` and `zone_id` (`area_id` is optional). The backend first tries `/api/v2/address-details` using the saved order address, then falls back to city/zone list matching. If automatic resolution cannot produce a reliable city/zone, **Sales -> Shipments -> Book Shipment** exposes manual CarryBee City ID / Zone ID / Area ID overrides.

Webhook endpoint:

```text
POST /api/v1/courier/webhooks/carrybee/
```

Configure the CarryBee webhook secret in the same environment credentials. The current integration expects the provider signature/token in `X-Carrybee-Webhook-Signature`; confirm the exact webhook-secret setup for your merchant account during sandbox onboarding.

**Cancellation:** the adapter calls `POST /api/v2/orders/{consignment_id}/cancel` with a cancellation reason. `API cancel` remains OFF by default so a merchant must validate cancellation in Sandbox before enabling it for Live parcels.

## Booking rules

The backend prevents booking when:

- the courier is inactive;
- current environment credentials are incomplete;
- the order is cancelled/delivered/returned/refunded;
- a non-COD online payment has not been server-verified as paid;
- the order already has another active shipment.

This prevents accidental duplicate bookings across different courier providers.

## Tracking -> order status sync

Provider tracking updates can advance the commerce order:

- picked / in transit -> `shipped`
- out for delivery -> `out_for_delivery`
- delivered -> `delivered`

Tracking never moves an order backward. Provider-specific statuses remain stored in `Shipment.provider_status` for audit/debugging.

A Steadfast partial-delivery status is deliberately **not** treated as a fully delivered order; it remains operationally open for merchant review instead of triggering full-order delivery side effects.

## Before going Live

1. Run migrations and back up the database.
2. Set `COURIER_CONFIG_ENCRYPTION_KEY`.
3. Start Redis, Celery Worker and Celery Beat.
4. Configure a sandbox provider first (Pathao, RedX or CarryBee).
5. Test connection.
6. Create a test order and move it to the configured auto-book status.
7. Confirm exactly one shipment is created.
8. Confirm tracking sync and event history.
9. Configure/test webhooks over public HTTPS.
10. Validate cancellation/return behavior with the provider merchant account.
11. Only then save Live credentials and switch the provider to Live mode.
