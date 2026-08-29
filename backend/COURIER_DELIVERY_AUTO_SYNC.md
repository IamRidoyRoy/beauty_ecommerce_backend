# Courier Delivered → Order Delivered Auto Sync

## Behaviour

When Pathao, Steadfast, RedX or CarryBee confirms a shipment as delivered:

1. Verified webhook delivery events are applied immediately when the provider payload contains an explicit delivered state.
2. Provider tracking reconciliation continues to query open shipments every 5 minutes.
3. A local reconciliation task runs every 1 minute and retries any Shipment=Delivered whose Order has not yet reached Delivered. This retry does not call the courier API.
4. Order transitions remain forward-only. Late courier callbacks never overwrite cancellation/return/refund workflows.
5. Moving an Order to Delivered executes the existing order business side effects, including reserved-stock consumption, fulfillment completion and the existing delivered-payment rule.

## Required services

Run both Celery worker and Celery Beat in production:

```bash
celery -A config worker -l info
celery -A config beat -l info
```

Configured schedules:

- Courier tracking API sync: every 5 minutes
- Delivered-order local reconciliation: every 1 minute

Provider webhooks should also be configured for near-real-time updates:

- `/api/v1/courier/webhooks/pathao/`
- `/api/v1/courier/webhooks/steadfast/`
- `/api/v1/courier/webhooks/redx/`
- `/api/v1/courier/webhooks/carrybee/`

No database migration is required for this update.
