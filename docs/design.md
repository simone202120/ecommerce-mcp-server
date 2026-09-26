# ecommerce-mcp-server — Design

## Goal
Expose an e-commerce database to any MCP client (Claude Desktop, IDEs, custom agents) through safe,
read-only tools, and show a LangGraph agent answering business questions by calling those tools.

Demo story (2 minutes): ask the agent "which products are running low and how much did they sell last
month?", show the tool calls; then show the same server connected to Claude Desktop.

## Data
PostgreSQL 17 + pgvector. Tables: customers, products (name, description, category, price, stock,
embedding vector), orders, order_items. Seed script with deterministic fake data (Faker, fixed seed):
~50 products, ~200 customers, ~1000 orders over the last 6 months. Product embeddings computed
locally with FastEmbed at seed time.

## MCP server (FastMCP, official `mcp` Python SDK)
Transports: stdio (Claude Desktop) and streamable HTTP (agent, Docker).
Tools (all read-only, parameterized SQL, row limits):
- `search_products(query, limit=5, category?)` — semantic search via pgvector cosine distance.
- `get_customer_orders(customer_email, limit=10)` — orders with items and totals.
- `sales_summary(start_date, end_date, group_by=day|week|month)` — revenue, orders, AOV.
- `top_products(start_date, end_date, limit=10, by=revenue|quantity)`.
- `low_stock_alert(threshold=10)` — products under threshold with last-30-days sales.
Resources: `schema://tables` (table descriptions). Clear error messages for bad input.

## Agent (LangGraph)
Prebuilt ReAct-style agent (`create_react_agent`) with tools loaded from the server via
`langchain-mcp-adapters` (`MultiServerMCPClient`, streamable HTTP). CLI: `uv run python -m
ecommerce_mcp.agent "question"`. Langfuse callback for traces.

## Non-goals
Write operations, auth on the MCP server, web UI (the demo uses CLI + Claude Desktop).

## Testing
- Unit: tool input validation, SQL builders/params, result formatting, agent wiring with a fake LLM
  and fake tools.
- Integration: seeded Postgres (CI service) — every tool against real data; FastMCP in-memory client
  lists and calls tools; pgvector search returns semantically related products.
- LLM: one agent question end-to-end.

## Deliverables
Docker compose (postgres, seed job, mcp server), README with Claude Desktop config snippet and
architecture diagram, `docs/architecture.md`, `docs/code-map.md`, CI green, coverage >= 80%.

## UI and demo polish

The UI is what the interviewer sees first: it must look clean and deliberate, not like a default
Streamlit script.

- Custom theme in `.streamlit/config.toml` (`[theme]`: base, primaryColor, backgroundColor,
  secondaryBackgroundColor, textColor, font, baseRadius) using the palette below. No heavy CSS hacks;
  at most a few lines of `st.markdown(..., unsafe_allow_html=True)` for spacing.
- `st.set_page_config` with title, icon and `layout="wide"`; a short header with the project name and
  a one-line description; a sidebar for settings and state.
- Long operations show progress (`st.status` / `st.progress` / `st.spinner`) with human-readable steps.
- Every screen has a useful empty state: 3 clickable example inputs that run a real demo.
- Results are presented, not dumped: containers with borders, badges, metrics, expanders. Raw JSON
  only in a collapsed "Raw response" expander.
- Show cost and speed of each run (tokens, estimated cost, latency) as small metrics: it proves the
  observability story. Link to the Langfuse trace when tracing is enabled.
- Errors are friendly `st.error` messages that say what to do, never stack traces.
- The UI talks to the FastAPI backend over HTTP (backend URL from settings), never imports `core/`.
- Keep it one file per page under `ui/`, small helpers in one module; no duplicated rendering code.

Scope addition: a small Streamlit chat UI for the agent (in addition to the CLI and Claude Desktop),
in `ui/`, talking to the agent through a thin FastAPI endpoint or directly to the agent module
(allowed here because the agent is the "backend"); keep it a single page.
Palette: dark base, background `#111318`, surface `#1A1D24`, text `#E8E9ED`, primary `#F59E0B`.
Layout: sidebar listing the MCP tools with their descriptions (fetched from the server) and a
connection status dot. Main area: chat; each agent turn shows the tool calls it made as compact
expandable cards (tool name, arguments, result preview), then the answer; numeric answers use
`st.metric` or a small chart. Examples: "Which products are running low and how did they sell last
month?", "Top 5 products by revenue this quarter", "Find products similar to 'wireless headphones'".
