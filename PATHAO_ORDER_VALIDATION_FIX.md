# Pathao Order Validation Fix

- Converts stored `+8801XXXXXXXXX` customer phones to Pathao's required `01XXXXXXXXX` format.
- Builds a descriptive recipient address from address + thana + district.
- Validates name, address and parcel weight before calling Pathao.
- Surfaces Pathao field-level `errors`/`validation` messages in the Courier Submission Result modal.
- Test Connection now also checks whether the configured Pickup Store ID belongs to the selected Sandbox/Live account when the store list is available.

No database migration is required.
