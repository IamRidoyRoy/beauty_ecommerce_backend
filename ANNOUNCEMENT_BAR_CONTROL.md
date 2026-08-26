# Announcement bar dashboard control

A new `common.AnnouncementMessage` model powers the storefront top ticker.

After replacing the backend, run from `beauty_ecommerce_backend/backend`:

```bash
python manage.py makemigrations common
python manage.py migrate
python manage.py seed_announcement_messages
```

The seed command is optional; it recreates the four current default storefront messages once so they are immediately editable from the dashboard.

Public endpoint: `GET /api/v1/announcement-messages/`

Dashboard CRUD endpoint: `GET/POST/PATCH/DELETE /api/v1/admin/announcement-messages/`

Fields: `text`, `icon`, `link_url`, `active`, `order`. Positive order values are shown first (`1`, `2`, `3` ...); `0` is treated as unprioritized / last.
