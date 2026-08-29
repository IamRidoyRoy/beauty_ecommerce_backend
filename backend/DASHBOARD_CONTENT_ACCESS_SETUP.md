# Dashboard Content & Staff Module Access Upgrade

## New controls

- Marketing -> Homepage Content -> Top promotional bar
- Marketing -> Homepage Content -> Homepage hero slider
- Users & Roles -> per-user dashboard module access

## Database migration

Run after replacing the backend:

```bash
python manage.py migrate siteconfig
python manage.py migrate accesscontrol
python manage.py migrate
```

Expected new migrations:

- `siteconfig.0003_announcement_item`
- `accesscontrol.0001_initial`

The access-control migration creates a new independent table and does not modify the legacy accounts table.

## Staff access behavior

Role permissions remain the capability ceiling. The selected module list further restricts access. The backend checks the module on management API requests, so hiding a menu is not the only protection.

Existing staff users with no access-profile row keep their existing role-default access. Once an admin saves module access for a staff user, the explicit selection is enforced.

Staff should sign in again after their module access is changed so the dashboard receives the newest module list in the authenticated user payload.

## Hero image guidance

- Desktop hero: 1600 x 600 px, WebP, <= 200 KB recommended
- Mobile hero: 800 x 1000 px, WebP, <= 200 KB recommended
