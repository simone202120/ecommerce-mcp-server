# Architecture

## Decisions

Important decisions and their trade-offs, in the order they were made.

### Validation split between the JSON schema and `core/validation.py`
Numeric bounds (`limit`, `threshold`) and enums (`group_by`, `by`) live in the tool JSON schema so the
LLM sees them and the MCP SDK rejects bad values before any code runs. Rules a schema cannot express
(start date after end date, maximum range span, blank queries, email format) live in
`core/validation.py` and raise `InvalidInputError`.
*Trade-off:* the core functions trust their numeric arguments, so any new caller must validate them.

### Revenue excludes cancelled orders
All revenue, order counts and "units sold" figures ignore orders with status `cancelled`; order
history for a customer still shows them.
*Trade-off:* a single, fixed business rule instead of a configurable filter.

### Date ranges are inclusive calendar days in UTC
`start_date`/`end_date` are converted to the half-open interval `[start 00:00 UTC, end+1 00:00 UTC)`
and capped at 731 days to bound the work (and rows) of a single call.
*Trade-off:* no per-user time zones.

### Embeddings passed as pgvector text literals
Query embeddings are sent as `'[0.1,0.2,...]'::vector` bind parameters instead of registering the
`pgvector` Python adapter.
*Trade-off:* one fewer dependency, at the cost of a slightly larger query payload.
