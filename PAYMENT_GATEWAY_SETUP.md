# Payment Gateway Upgrade

This build adds verified online-payment flows for **SSLCOMMERZ, bKash and Nagad** while preserving COD.

## What is included

- Hosted/payment URL initiation from checkout.
- Public retry endpoint protected by an unguessable payment UUID (`public_token`).
- SSLCOMMERZ success/fail/cancel callbacks and IPN.
- bKash callback + webhook ingestion.
- Nagad callback + webhook ingestion.
- Server-side gateway verification before a payment can become `paid`.
- Amount, currency, order/reference validation.
- Idempotent webhook event log.
- Reconciliation audit log for every gateway verification.
- Admin/finance manual `Reconcile` action.
- Celery automatic reconciliation every 10 minutes for recent open payments.
- Safe payment failure/cancel handling without deleting the order.
- Storefront retry flow after a failed/cancelled gateway session.
- Meta Purchase server event only after verified online payment settlement. COD remains order-placement based.

## Required environment variables

Set these in the backend environment. Never expose merchant secrets to Next.js or the dashboard.

```env
PAYMENT_API_BASE_URL=https://api.yourdomain.com
PAYMENT_STOREFRONT_URL=https://www.yourdomain.com
PAYMENT_GATEWAY_TIMEOUT=20

# SSLCOMMERZ
SSLCOMMERZ_SANDBOX=true
SSLCOMMERZ_STORE_ID=
SSLCOMMERZ_STORE_PASSWORD=

# bKash Tokenized Checkout
BKASH_SANDBOX=true
BKASH_BASE_URL=
BKASH_APP_KEY=
BKASH_APP_SECRET=
BKASH_USERNAME=
BKASH_PASSWORD=

# Nagad Online PG
NAGAD_SANDBOX=true
NAGAD_BASE_URL=
NAGAD_MERCHANT_ID=
NAGAD_MERCHANT_NUMBER=
NAGAD_MERCHANT_PRIVATE_KEY=
NAGAD_GATEWAY_PUBLIC_KEY=
NAGAD_CLIENT_IP=
NAGAD_API_VERSION=v-0.2.0
NAGAD_CLIENT_TYPE=PC_WEB
NAGAD_CURRENCY_CODE=050
```

`PAYMENT_API_BASE_URL` must be a publicly reachable HTTPS backend URL because gateways call the callback/IPN endpoints directly.

For bKash and Nagad, use the exact base URL/API version and credentials supplied for your merchant account. Merchant environments can differ by onboarding product/version. Nagad commonly requires merchant server IP/domain/callback whitelisting; use the values supplied during onboarding.

## Public endpoints

```text
POST /api/v1/payments/<public_token>/initiate/

GET|POST /api/v1/payments/sslcommerz/callback/success/
GET|POST /api/v1/payments/sslcommerz/callback/fail/
GET|POST /api/v1/payments/sslcommerz/callback/cancel/
POST     /api/v1/payments/sslcommerz/callback/ipn/

GET|POST /api/v1/payments/bkash/callback/
GET|POST /api/v1/payments/nagad/callback/
POST     /api/v1/payments/webhooks/bkash/
POST     /api/v1/payments/webhooks/nagad/
```

## Admin endpoints

```text
GET  /api/v1/admin/payments/
POST /api/v1/admin/payments/<id>/reconcile/
GET  /api/v1/admin/payments/<id>/reconciliations/
```

Payment state is intentionally read-only from the management UI. Admins cannot manually set an online payment to `paid`; they must reconcile it against the gateway.

## Checkout behavior

1. Checkout atomically creates the order, reserves/reduces inventory according to the existing commerce rules, and creates a pending payment.
2. For an online method, the backend creates a gateway session and returns `payment.payment_url`.
3. The storefront clears the completed cart, stores only the retry/public payment context in `sessionStorage`, and redirects the shopper to the gateway.
4. The gateway calls the backend callback/IPN.
5. The backend queries/verifies the transaction directly with the gateway.
6. Only a verified matching amount/currency/reference can transition to `paid`.
7. The shopper is redirected to `/order-success/<order>?payment=<status>`.
8. Failed/cancelled/pending sessions can be retried without creating another order.

## Database migration note

This repository originally contains migrations only for the tracking app. Because the other domain apps are currently migration-less, do **not** add a standalone payments migration with a dependency on non-existent order/account migrations.

Before deploying this upgrade, create and commit a complete migration baseline for the repository in one environment:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py check
python manage.py test apps.payments apps.orders
```

Review the generated migrations before running them against an existing production database. If production tables were previously created without migrations, use a proper baseline/fake-initial migration procedure instead of blindly applying initial migrations.

## Celery reconciliation

`config/settings/base.py` now schedules:

```text
apps.payments.tasks.reconcile_open_gateway_payments
```

every 600 seconds. Celery worker + beat must both be running for automatic reconciliation. Recent initiated payments that are still pending/authorized are re-queried for up to three days so a missed callback can recover safely. Failed/cancelled payments remain available for explicit finance reconciliation when needed.

## Production checklist

- Switch each provider from sandbox to live only after sandbox/UAT passes.
- Configure HTTPS callback/IPN URLs with each gateway.
- Whitelist production IP/domain where the provider requires it.
- Keep gateway secrets only in backend environment/secrets manager.
- Start Celery worker and Celery beat.
- Test success, cancel, fail, duplicate webhook, delayed callback, and manual reconciliation flows.
- Confirm the exact charged amount and transaction reference in the provider merchant portal.
- Confirm Meta Purchase fires only after verified online payment settlement.
