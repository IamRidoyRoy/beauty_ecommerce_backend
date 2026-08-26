# Commercial reporting and delivered-payment update

## Revenue recognition
Commercial KPIs and sales/profit reports now count an order as soon as it is placed. `payment_status` does not gate operational revenue.

Excluded commercial order states:
- cancelled
- partially_returned
- returned
- refunded

`return_requested` remains included until the return is actually received/completed.

## Delivered = paid
When an order transitions to `delivered`:
- `Order.payment_status` becomes `paid`
- pending/authorized Payment rows for that order become `paid`
- `paid_at` is recorded

## Profit report
Profit now uses the same commercial-order rule and exposes order count, order revenue, product revenue, discounts, shipping revenue, tax, COGS, refund impact, gross profit, and margin.

No database migration is required.
