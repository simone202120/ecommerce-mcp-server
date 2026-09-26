# ecommerce-mcp-server

MCP server exposing safe, read-only tools over an e-commerce PostgreSQL database (with pgvector
semantic product search), plus a LangGraph agent that uses it from a CLI, a Streamlit chat UI and
Claude Desktop.

```mermaid
flowchart LR
    subgraph Clients
        CD[Claude Desktop] -- stdio --> S
        CLI[Agent CLI] -- streamable HTTP --> S
        UI[Streamlit UI] --> A[LangGraph agent] -- streamable HTTP --> S
        CLI --> A
    end
    A -- OpenRouter --> LLM[(LLM)]
    A -. optional .-> LF[(Langfuse)]
    S[FastMCP server<br/>5 read-only tools<br/>schema://tables] --> C[core: validation,<br/>SQL, models]
    C -- read-only pool --> PG[(PostgreSQL 17<br/>+ pgvector)]
    S -- query embedding --> FE[FastEmbed<br/>bge-small-en-v1.5]
    SEED[seed job<br/>Faker + FastEmbed] --> PG
```

## Tools

| Tool | What it answers |
| --- | --- |
| `search_products(query, limit=5, category?)` | Semantic search (pgvector cosine distance) |
| `get_customer_orders(customer_email, limit=10)` | A customer's orders with items and totals |
| `sales_summary(start_date, end_date, group_by=day\|week\|month)` | Revenue, orders, average order value |
| `top_products(start_date, end_date, limit=10, by=revenue\|quantity)` | Best sellers in a period |
| `low_stock_alert(threshold=10)` | Products under a stock threshold with last-30-days sales |

Resource `schema://tables` describes the data model. Every tool is read-only by construction: the
connection pool opens sessions with `default_transaction_read_only=on` and a statement timeout, all
SQL is parameterized, and every multi-row query has a row limit. Bad arguments get clear error
messages (e.g. `start_date (2026-09-01) must be on or before end_date (2026-08-01)`).

## Quick start (Docker)

```bash
cp .env.example .env         # add OPENROUTER_API_KEY; Langfuse keys are optional
docker compose up --build    # postgres, seed job, MCP server (:8000), UI (:8501)
```

- UI: <http://localhost:8501>
- Agent CLI: `docker compose exec mcp python -m ecommerce_mcp.agent "Which products are running low and how much did they sell last month?"`

## Local development

```bash
uv sync
docker compose up -d postgres
uv run python -m ecommerce_mcp.infra.seed                       # schema + deterministic data
uv run python -m ecommerce_mcp.server --transport streamable-http
uv run python -m ecommerce_mcp.agent "Top 5 products by revenue this quarter"
uv run streamlit run src/ecommerce_mcp/ui/app.py
```

The CLI prints the tool calls, the answer, latency, tokens, the estimated cost and the Langfuse
trace link (when tracing is configured).

## Claude Desktop

Seed the database first, then add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ecommerce": {
      "command": "uv",
      "args": ["--directory", "/path/to/ecommerce-mcp-server", "run", "python", "-m", "ecommerce_mcp.server"],
      "env": { "DATABASE_URL": "postgresql://shop:shop@localhost:5432/shop" }
    }
  }
}
```

## Configuration

All settings are environment variables (or `.env`), read by `src/ecommerce_mcp/config.py`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql://shop:shop@localhost:5432/shop` | PostgreSQL connection |
| `DB_POOL_SIZE` / `DB_STATEMENT_TIMEOUT_MS` | `5` / `5000` | Tool connection pool |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | FastEmbed model (must output 384-dim vectors) |
| `MCP_HOST` / `MCP_PORT` | `127.0.0.1` / `8000` | Streamable HTTP bind address |
| `MCP_URL` | `http://localhost:8000/mcp` | Where the agent and UI reach the server |
| `OPENROUTER_API_KEY` | — | LLM access (OpenRouter, OpenAI-compatible) |
| `LLM_MODEL` | `google/gemini-3.8-flash` | Chat model |
| `LLM_TIMEOUT_SECONDS` / `AGENT_MAX_STEPS` | `60` / `12` | Agent limits |
| `LLM_INPUT_USD_PER_MTOK` / `LLM_OUTPUT_USD_PER_MTOK` | `0.30` / `2.50` | Cost estimate shown per run |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | empty | Optional tracing |

## Tests

```bash
uv run pytest tests/unit -q          # fast, no services
uv run pytest -m integration         # needs a running postgres (seeds it)
uv run pytest -m llm                 # one real agent question end to end (costs money)
```

CI runs lint, format, `mypy --strict`, vulture, deptry, and unit + integration tests with coverage
(>= 80%) on a pgvector service, and builds the Docker image on pull requests.

## Docs

- [`docs/design.md`](docs/design.md): scope and requirements
- [`docs/architecture.md`](docs/architecture.md): layers, request flow and decisions with trade-offs
- [`docs/code-map.md`](docs/code-map.md): generated module import graph

## Development

This project is developed with an AI-assisted workflow using [Claude Code](https://claude.com/claude-code):
project context in [`CLAUDE.md`](CLAUDE.md), specialized agents, slash commands and hooks in
[`.claude/`](.claude/) (auto-formatting, secret protection, session context).

## License

MIT
