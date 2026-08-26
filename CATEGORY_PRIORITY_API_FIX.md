# Category priority API fix

The public category endpoint now treats `order=0` as the default/unprioritized value.

Public ordering semantics:
- order 1, 2, 3, ... first
- order 0/unset after explicitly prioritized categories
- name and id are stable tie-breakers

The public category endpoint is also unpaginated so the storefront always receives the complete parent/subcategory tree.

No database migration is required.
