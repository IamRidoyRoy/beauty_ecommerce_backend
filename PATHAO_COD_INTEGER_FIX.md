# Pathao COD Integer Fix

Pathao validates `amount_to_collect` as an integer. The commerce platform keeps order totals as Decimal values for accounting, so the Pathao adapter now converts only the provider payload to whole BDT using `ROUND_HALF_UP`.

Examples:
- `709.00` -> `709`
- `2577.49` -> `2577`
- `2577.50` -> `2578`

The stored order total is not changed.
