"""PostgreSQL access: a read-only connection pool for the tools and schema setup for the seed."""

from importlib.resources import files
from typing import Any

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from ecommerce_mcp.config import Settings


def read_only_pool(settings: Settings) -> AsyncConnectionPool[AsyncConnection[Any]]:
    """Opens lazily; every session is read-only and time-limited, whatever SQL a tool runs."""
    options = (
        "-c default_transaction_read_only=on"
        f" -c statement_timeout={settings.db_statement_timeout_ms}"
        " -c timezone=UTC"
    )
    return AsyncConnectionPool(
        settings.database_url,
        min_size=1,
        max_size=settings.db_pool_size,
        kwargs={"options": options, "autocommit": True},
        open=False,
    )


async def apply_schema(conn: AsyncConnection[Any]) -> None:
    schema = files("ecommerce_mcp.infra").joinpath("schema.sql").read_text(encoding="utf-8")
    await conn.execute(schema)
