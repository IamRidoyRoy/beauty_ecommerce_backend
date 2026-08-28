# Google Tag Manager + Meta Pixel + Conversions API

This storefront uses a two-channel tracking design:

1. **Browser channel:** the storefront loads the Google Tag Manager Web container configured in BEAUTYOPS and pushes structured `meta_event` events to `window.dataLayer`. Meta Pixel must be installed inside that GTM container.
2. **Server channel:** Django sends the same commerce events directly to Meta Conversions API. Browser and server events share the same `event_id` so Meta can deduplicate them.

The tracking configuration is controlled from **BEAUTYOPS → Marketing → Pixel & Tracking**. No storefront rebuild is required when IDs, token, event switches, or the master enable switch are changed.

## 1. Backend deployment

From `beauty_ecommerce_backend/backend`:

```bash
pip install -r requirements.txt
python manage.py migrate
```

The migration creates the singleton tracking settings table and the CAPI event-delivery log.

## 2. Configure Meta in BEAUTYOPS

Open **Marketing → Pixel & Tracking** and enter:

- Google Tag Manager Web Container ID, for example `GTM-ABC1234`
- Meta Pixel ID
- Meta Conversions API access token
- Graph API version (the project is pinned by default instead of floating automatically)
- Currency, normally `BDT`
- Optional Meta Test Event Code while validating the setup

Enable:

- **Enable marketing tracking**
- **Browser events through GTM**
- **Server events through Meta CAPI**

Individual events can be turned on/off from the same page.

## 3. One-time Google Tag Manager setup

The app cannot publish or modify your remote Google Tag Manager container without access to your Google account. Do this one-time setup inside the GTM Web container whose ID you entered in BEAUTYOPS.

### Data Layer Variables

Create Data Layer Variables for:

- `meta_pixel_id`
- `meta_event_name`
- `event_id`
- `custom_data`

Use Data Layer Version 2.

### Trigger

Create a **Custom Event** trigger:

- Event name: `meta_event`
- Fire on: All Custom Events matching this event name

### Meta Pixel tag

Use a trusted Meta Pixel GTM template if your container has one. Map:

- Pixel ID → `{{DLV - meta_pixel_id}}`
- Event name → `{{DLV - meta_event_name}}`
- Event ID / deduplication ID → `{{DLV - event_id}}`
- Event parameters → `{{DLV - custom_data}}`

Attach the `meta_event` trigger.

If your template does not support a dynamic event ID, use a Custom HTML tag equivalent to the following implementation:

```html
<script>
(function () {
  var pixelId = {{DLV - meta_pixel_id}};
  var eventName = {{DLV - meta_event_name}};
  var eventId = {{DLV - event_id}};
  var params = {{DLV - custom_data}} || {};
  if (!pixelId || !eventName) return;

  if (!window.fbq) {
    !function(f,b,e,v,n,t,s){
      if(f.fbq)return;n=f.fbq=function(){n.callMethod?
      n.callMethod.apply(n,arguments):n.queue.push(arguments)};
      if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
      n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;
      s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)
    }(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
  }

  window.__beautyMetaPixels = window.__beautyMetaPixels || {};
  if (!window.__beautyMetaPixels[pixelId]) {
    fbq('init', pixelId);
    window.__beautyMetaPixels[pixelId] = true;
  }

  fbq('track', eventName, params, { eventID: eventId });
})();
</script>
```

Do **not** add a second independent PageView tag if the `meta_event` tag already handles `PageView`, otherwise browser events can be duplicated.

Publish the GTM container after testing it in Preview mode.

## 4. Events implemented

The storefront/server integration supports:

- `PageView`
- `ViewContent`
- `Search`
- `AddToCart`
- `AddToWishlist`
- `InitiateCheckout`
- `Purchase`

`Purchase` is authoritative on the Django checkout server. The browser pushes a Pixel `Purchase` with the exact same `event_id` (`purchase:<order number>`) so Meta can deduplicate Pixel and CAPI delivery.

## 5. Test the connection

1. Add your Meta Test Event Code in BEAUTYOPS.
2. Click **Send CAPI Test**.
3. Confirm the event in Meta Events Manager / Test Events.
4. Open the storefront and test product view, search, add-to-cart, checkout and a test order.
5. Review **Recent server events** on the BEAUTYOPS tracking page.
6. After validation, remove the Test Event Code before normal production operation.

## 6. Consent mode

If **Require marketing consent** is enabled in BEAUTYOPS, the storefront shows an Allow/Decline marketing banner. GTM and CAPI marketing events do not run until the shopper grants consent. Essential cart, checkout and account behavior continues to work if they decline.

## 7. Security and production notes

- The CAPI access token is encrypted before it is stored and is never returned by the public storefront configuration endpoint.
- Recent event logs contain event metadata and delivery results, not the raw token.
- Email, phone and external user ID are normalized and SHA-256 hashed before they are sent as CAPI matching fields.
- `_fbp` and `_fbc`, browser user-agent and client IP are forwarded by Django when available.
- Configure your reverse proxy so `X-Forwarded-For` can only be supplied by trusted infrastructure.
- Keep Django `SECRET_KEY` stable. Changing it makes an already-encrypted CAPI token unreadable and you will need to save the token again.
- Tracking failures are non-blocking: an unavailable Meta endpoint must never prevent a successful cart or checkout operation.
