# Branding & Theme Control

The dashboard now controls storefront and dashboard identity from **Settings → Branding & Theme**.

## Database

Run after deploying this version:

```bash
python manage.py migrate siteconfig
python manage.py migrate
```

This creates `siteconfig_sitebrandingsettings`. No fake migration is required because `siteconfig` is a new app.

## Dashboard controls

- Website display mode: Text Name / Logo Image
- Website name and tagline
- Website logo upload/remove
- Dashboard display mode: Text Name / Logo Image
- Dashboard name and tagline
- Dashboard logo upload/remove
- Website primary color
- Website secondary color

Logo files are stored through Django's configured `MEDIA_ROOT`. Production must serve `/media/` through the configured web server/object storage/CDN.

## APIs

Public visual config:

`GET /api/v1/site-settings/`

Management config:

`GET /api/v1/admin/site-settings/`

`PATCH /api/v1/admin/site-settings/` (JSON or multipart form-data)

The management endpoint is restricted to Super Admin, Admin and Manager roles.
