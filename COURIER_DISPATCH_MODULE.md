# Courier Dispatch Module

## Operational workflow

`Pending → Confirmed → Processing → Packed → Shipped → Out for Delivery → Delivered`

The legacy intermediate pre-shipment state is no longer part of the order lifecycle. Migration `shipping.0004_packed_courier_workflow` normalizes existing rows to `packed`.

## Dashboard workflow

Open **Sales → Courier**.

- The table contains `Packed` and `Shipped` orders.
- Only `Packed` orders can be selected.
- One or many Packed orders can be submitted to the selected active courier.
- A successful courier API booking immediately changes the order to `Shipped` and stores the courier/tracking shipment.
- Shipped rows remain visible but are read-only for courier submission.
- Details open in a modal; invoice opens the existing invoice view.
- Failed orders in a bulk request are reported independently and do not roll back successful bookings.

## APIs

- `GET /api/v1/admin/shipments/courier-orders/`
- `POST /api/v1/admin/shipments/submit-orders/`

Example batch request:

```json
{
  "order_ids": [101, 102, 103],
  "provider": "pathao"
}
```

The provider must be active and configured in **Settings → Courier Integrations**.

## Auto booking

Auto booking is now fixed to the `Packed` status. When Auto book is enabled, the highest-priority eligible courier can submit the order automatically. Disable Auto book for a fully manual selection workflow from Sales → Courier.
