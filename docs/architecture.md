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

### Defense in depth for "read-only"
Tool sessions are opened with `default_transaction_read_only=on` and a `statement_timeout`, on top of
the SELECT-only queries. Even a future query bug cannot write to the database or run unbounded.
*Trade-off:* the seed job needs its own read-write connection instead of the pool.

### No vector index on `products.embedding`
With about 50 products an exact sequential scan is faster than an HNSW/IVFFlat index and always
returns the true nearest neighbours.
*Trade-off:* a larger catalog needs `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`.

### Product catalog as hand-written CSV, customers and orders from Faker
Semantic search is only convincing with realistic names and descriptions, which Faker does not
produce; customers and orders are generated with a fixed seed relative to the seed time, so "last
month" always has data.
*Trade-off:* re-running the seed on another day shifts the dates (the same seed and `now` always
produce identical data).

### `mcp` SDK pinned below 2.0
`mcp` 2.x renames `FastMCP` to `MCPServer`, and `langchain-mcp-adapters` still requires `mcp<2`.
The server uses FastMCP from `mcp` 1.x, as the design asks.
*Trade-off:* a migration is needed once the adapters support `mcp` 2.

### Database errors are masked at the tool boundary
The MCP SDK sends any exception message to the client verbatim. Domain errors (`ShopError`) are
written to be shown; `psycopg` errors (including pool timeouts) are logged with their stack trace
and replaced by "the database query failed; try again later" so hosts and SQL never leak.
*Trade-off:* clients cannot tell a timeout from a lost connection.
### `create_agent` instead of the deprecated `create_react_agent`
LangGraph 1.x deprecates `langgraph.prebuilt.create_react_agent` in favour of
`langchain.agents.create_agent`, which builds the same prebuilt ReAct loop on LangGraph.
*Trade-off:* one extra dependency (`langchain`) to avoid shipping on a deprecated API.

### Agent CLI prints with `sys.stdout.write`
Logs go to stderr through `logging`; the agent's answer is the CLI's output, not a log record.
*Trade-off:* the one place in `src/` that writes to stdout directly.

### Docker image bakes the embedding model
The image downloads the FastEmbed model at build time and runs with `HF_HUB_OFFLINE=1`, so the seed
job and the server start without network access to Hugging Face. One image serves the seed job, the
server and the agent CLI. A PR-only CI job builds the image without pushing it.
*Trade-off:* a larger image (~70 MB of model weights) for predictable, offline startup.

### Streamlit UI calls the agent module directly
`docs/design.md` allows the chat UI to call either a thin FastAPI endpoint or the agent module.
The UI imports only `agent.runner` (never `core/`), which reaches the tools over MCP streamable HTTP,
exactly like the CLI.
*Trade-off:* no extra HTTP service to build and deploy, but the UI process needs the LLM key.

### Run cost is an estimate from configured prices
Token counts come from the LLM's usage metadata; the dollar figure multiplies them by
`LLM_INPUT_USD_PER_MTOK` / `LLM_OUTPUT_USD_PER_MTOK`.
*Trade-off:* no dependency on provider-specific billing fields, at the price of keeping the two
settings in line with the chosen model.

### Tool cards use tabs for the raw response
Streamlit does not allow nested expanders, so each tool card is an expander with a "Preview" tab
(table, metrics or chart) and a "Raw response" tab holding the collapsed JSON. Cards with charts
(`sales_summary`, `top_products`) start open because they carry the answer's numbers.
*Trade-off:* one extra click to reach the raw JSON.
