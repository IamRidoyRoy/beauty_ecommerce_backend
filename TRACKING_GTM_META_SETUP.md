# Google Tag Manager + Meta Pixel storefront tracking

The singleton `CheckoutSettings` now stores:

- `tracking_enabled`
- `google_tag_manager_id` (example `GTM-ABC1234`)
- `meta_pixel_id`

The dashboard edits these values through `PATCH /api/v1/admin/checkout-settings/`.
The storefront reads the public-safe values from `GET /api/v1/tracking-settings/`.

## Database migration

This source bundle intentionally does not ship project migration history. After replacing the backend, run:

```bash
python manage.py makemigrations common
python manage.py migrate
```

## GTM container one-time configuration

The storefront loads the GTM container dynamically and pushes `meta_pixel_id` into the dataLayer before GTM boots.
Create a Data Layer Variable in GTM named `meta_pixel_id`. Use that variable in your Meta Pixel base tag.

Recommended dataLayer events emitted by the storefront:

- `page_view` -> Meta `PageView`
- `view_item` -> Meta `ViewContent`
- `add_to_cart` -> Meta `AddToCart`
- `add_to_wishlist` -> Meta `AddToWishlist`
- `begin_checkout` -> Meta `InitiateCheckout`
- `purchase` -> Meta `Purchase`

Each commerce push also contains `meta_event` and useful commerce fields such as currency, value, content IDs, transaction ID, and ecommerce payload when available.

Do not put a Meta Pixel access token in this settings screen. The browser only needs the public Pixel ID.

## Recommended GTM tags

### 1) Variable
Create **Data Layer Variable**: `DLV - Meta Pixel ID` with Data Layer Variable Name `meta_pixel_id`.

### 2) Meta base/init tag
Create a Custom HTML tag triggered by the custom event `site_tracking_config`. Initialize the Pixel with `{{DLV - Meta Pixel ID}}`. Do not fire PageView in the base tag, because the storefront emits its own `page_view` event for initial load and SPA navigation.

### 3) Event tags
Create Custom Event triggers for the storefront event names and map them to Meta events using the `meta_event` dataLayer field. The frontend already emits `meta_value`, `meta_currency`, `meta_content_ids`, `meta_content_name`, and `transaction_id` where available.

Use GTM Preview plus Meta Events Manager Test Events before publishing.
