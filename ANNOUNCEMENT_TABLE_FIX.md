# Announcement Messages database setup

The Announcement Messages dashboard depends on the `common.AnnouncementMessage` database table.

After replacing the backend, run from `beauty_ecommerce_backend/backend`:

```bash
python manage.py setup_storefront_controls --seed
```

The command safely generates the `common` migration against the migration history already present in your local project, applies all pending migrations, and optionally seeds the default messages.

Equivalent manual commands:

```bash
python manage.py makemigrations common
python manage.py migrate
python manage.py seed_announcement_messages
```

No existing order/product/customer data is deleted.
