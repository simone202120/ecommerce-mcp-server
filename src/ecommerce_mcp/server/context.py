"""Per-server resources shared by all tool calls, created once in the server lifespan."""

from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import Context
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from ecommerce_mcp.core.service import EmbedQuery


@dataclass(frozen=True)
class AppContext:
    pool: AsyncConnectionPool[AsyncConnection[Any]]
    embed_query: EmbedQuery


def app_context(ctx: Context[Any, AppContext, Any]) -> AppContext:
    return ctx.request_context.lifespan_context
