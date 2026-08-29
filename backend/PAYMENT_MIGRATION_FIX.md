# Payment schema migration fix

The payment gateway upgrade adds new database fields and a reconciliation table. Existing databases created before this upgrade already contain the legacy `payments_payment` and `payments_paymentwebhookevent` tables, but they do not contain the new columns.

## Existing database (important)

Run these commands from the folder containing `manage.py`:

```bash
python manage.py migrate payments 0001 --fake-initial
python manage.py migrate payments
python manage.py migrate
```

Why the first command is required: `0001_initial` represents the payment tables that already exist in your database. `--fake-initial` records that baseline without trying to recreate those tables. `0002_gateway_upgrade` then adds the new fields safely.

Do **not** fake `0002_gateway_upgrade`.

## Verify

```bash
python manage.py showmigrations payments
```

Expected:

```text
payments
 [X] 0001_initial
 [X] 0002_gateway_upgrade
```

Then start the API again.
