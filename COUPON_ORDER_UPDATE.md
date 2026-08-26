# Dashboard order coupon update

- Adds `POST /api/v1/admin/orders/validate-coupon/`.
- Validates coupon rules against the exact draft order items and customer phone.
- Returns coupon discount, automatic promotion discount, total estimated discount, eligible subtotal, and free-shipping state.
- Order creation still revalidates the coupon inside the checkout transaction.
- New orders snapshot coupon discount metadata inside `promotion_snapshot` without adding a database column.
