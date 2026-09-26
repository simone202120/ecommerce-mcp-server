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
