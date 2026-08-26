# Public category priority ordering

The public category endpoint now explicitly orders active categories by hierarchy/priority before serialization.
The frontend also independently sorts each hierarchy level by the serialized `order` value.

No schema change or migration is required; this uses the existing Category.order field.
