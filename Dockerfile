# One image for the seed job, the MCP server and the agent CLI.
FROM python:3.12-slim-bookworm AS builder

RUN pip install --no-cache-dir "uv>=0.8,<0.9"
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev

# Bake the embedding model into the image so containers start without downloading it.
ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
ENV FASTEMBED_CACHE_PATH=/app/models
RUN .venv/bin/python -c "from fastembed import TextEmbedding; TextEmbedding('${EMBEDDING_MODEL}')"

FROM python:3.12-slim-bookworm

RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
USER app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/app/models \
    HF_HUB_OFFLINE=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

EXPOSE 8000
CMD ["python", "-m", "ecommerce_mcp.server", "--transport", "streamable-http"]
