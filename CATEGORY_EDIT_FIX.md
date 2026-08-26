# Category edit fix

- `CategorySerializer` accepts optional image input and preserves the existing image on metadata-only PATCH requests containing `image: null`.
- Public and admin category querysets prioritize positive `order` values before 0/unset.
- No database migration is required.
