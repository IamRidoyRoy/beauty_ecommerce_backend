# Category priority resequencing

Category display order is sibling-scoped and deterministic:

- `1` is the first category under a parent.
- `2` is second, etc.
- `0` is unprioritized and appears after prioritized categories.
- assigning an occupied priority inserts the edited category at that position and shifts/resequences the other prioritized siblings.
- parent categories and each subcategory group are ordered independently.

No migration is required.
