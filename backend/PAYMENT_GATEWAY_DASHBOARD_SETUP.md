# Dashboard-managed Payment Gateways

Payment gateway credentials are now managed from the Management Dashboard instead of requiring code changes.

## 1. Migrate

```bash
python manage.py migrate
```

Migration `payments.0003_payment_gateway_config` creates SSLCOMMERZ, bKash and Nagad configuration rows. They start inactive so no incomplete gateway is exposed at checkout.

## 2. Encryption key

Credentials saved from Dashboard are encrypted before being stored in the database.

For production set a stable key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Put the output in your backend environment:

```env
PAYMENT_CONFIG_ENCRYPTION_KEY=<generated-key>
```

Do not rotate/delete this value without re-encrypting the stored gateway configuration. In development, if this variable is empty, the app derives an encryption key from Django `SECRET_KEY`.

## 3. Configure from Dashboard

Open **Settings → Payment Gateways**.

For each provider you can:

- Configure Sandbox credentials
- Configure Live credentials separately
- Switch **Sandbox Mode** on/off
- Activate/deactivate checkout visibility
- Change display name and sort order
- Optionally override gateway base URLs

A gateway cannot be activated until all required credentials for the selected environment are saved.

## 4. Checkout behavior

`GET /api/v1/payment-methods/` returns only COD plus active/configured online gateways. The storefront reads this endpoint dynamically, so deactivating a gateway removes it from checkout without a frontend deployment.

The backend also validates the selected method during checkout, so a stale browser cannot use a gateway that was disabled after the page loaded.

## 5. Safe environment switching

The environment used to initiate an online payment is saved in `Payment.metadata.gateway_environment`. If the admin later switches from Sandbox to Live (or the reverse), callbacks/reconciliation for already initiated payments continue using their original environment.

## 6. Existing `.env` credentials

Legacy gateway variables are retained only as a reconciliation fallback for existing transactions created before this dashboard configuration upgrade. New online checkout availability is controlled by the database configuration.
