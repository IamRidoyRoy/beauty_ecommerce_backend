# Category Search Hierarchy Update

`ProductFilter.category` now resolves the selected active category and all active descendants.

This means:
- selecting a leaf category returns that category's products;
- selecting a parent category returns products assigned directly to the parent plus products assigned to any nested subcategory;
- no database migration is required.
