# Order workflow backend update

- Admin customer list now exposes `checkout_address` from the default/latest saved address.
- Admin product and variant responses expose `available_stock`; products also expose `primary_image`.
- Admin order item validation rejects quantities above sellable stock with a useful field error.
- New order image snapshots use stable `/media/...` URLs.
- No database schema change is required by this update.
