# Homepage Content Control

Homepage promotional content is managed from **Marketing → Homepage Content** in the management dashboard.

## Managed slots

- Promo banner — left
- Promo banner — right
- Editorial / ingredient spotlight

Each slot supports:

- Active / hidden
- Eyebrow / badge
- Title
- Subtitle
- CTA label
- Optional uploaded image
- Image alt text
- Background, text and media-panel colors
- Destination type and destination value

## Destination types

- Category → `/category/<slug>`
- Brand → `/brand/<slug>`
- Product → `/product/<slug>`
- Products page → `/products` plus an optional query string
- Search → `/search?q=<query>`
- Custom → any internal path beginning with `/` or an absolute `http(s)` URL
- No link

## API

Public storefront:

`GET /api/v1/homepage-banners/`

Dashboard:

`GET /api/v1/admin/homepage-banners/`

`PATCH /api/v1/admin/homepage-banners/<id>/`

## Migration

Run:

```bash
python manage.py migrate siteconfig
python manage.py migrate
```

Migration `siteconfig.0002_homepage_banner` creates the three fixed slots and seeds the previous hardcoded content as defaults.
