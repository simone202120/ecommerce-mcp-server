"""MCP tool definitions: argument schemas and descriptions, delegating the work to core.service."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Any

import psycopg
from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from ecommerce_mcp.core import service
from ecommerce_mcp.core.errors import ShopError
from ecommerce_mcp.core.models import (
    CustomerOrders,
    GroupBy,
    LowStockReport,
    ProductSearchResult,
    RankBy,
    SalesSummary,
    TopProducts,
)
from ecommerce_mcp.core.validation import MAX_QUERY_LENGTH
from ecommerce_mcp.server.context import AppContext, app_context

logger = logging.getLogger(__name__)

READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)

ToolContext = Context[Any, AppContext, Any]
StartDate = Annotated[date, Field(description="First day included, YYYY-MM-DD (UTC).")]
EndDate = Annotated[date, Field(description="Last day included, YYYY-MM-DD (UTC).")]


def _limit(default_help: str) -> Any:
    return Field(ge=1, le=service.MAX_LIMIT, description=f"Maximum rows to return. {default_help}")


@asynccontextmanager
async def _connection(app: AppContext) -> AsyncIterator[psycopg.AsyncConnection[Any]]:
    """Yields a pooled connection; database failures become a generic, safe error message."""
    try:
        async with app.pool.connection() as conn:
            yield conn
    except psycopg.Error as exc:
        logger.exception("Database error while running a tool")
        raise ShopError("the database query failed; try again later") from exc


def register_tools(server: FastMCP[AppContext]) -> None:
    @server.tool(annotations=READ_ONLY)
    async def search_products(
        ctx: ToolContext,
        query: Annotated[
            str,
            Field(
                min_length=1,
                max_length=MAX_QUERY_LENGTH,
                description="What the customer is looking for, in natural language "
                "(e.g. 'gift for a runner').",
            ),
        ],
        limit: Annotated[int, _limit("Default 5.")] = 5,
        category: Annotated[
            str | None,
            Field(
                description="Optional exact category name, case-insensitive: Electronics, "
                "Home & Kitchen, Sports & Outdoors, Books, Clothing, Beauty & Personal Care."
            ),
        ] = None,
    ) -> ProductSearchResult:
        """Semantic product search: finds products whose meaning matches the query, even without
        shared keywords. Returns price, stock and a similarity score (higher is closer)."""
        app = app_context(ctx)
        async with _connection(app) as conn:
            return await service.search_products(conn, app.embed_query, query, limit, category)

    @server.tool(annotations=READ_ONLY)
    async def get_customer_orders(
        ctx: ToolContext,
        customer_email: Annotated[str, Field(description="The customer's email address.")],
        limit: Annotated[int, _limit("Default 10.")] = 10,
    ) -> CustomerOrders:
        """A customer's most recent orders (newest first), each with status, line items and
        total. Fails with a clear message if no customer has that email."""
        app = app_context(ctx)
        async with _connection(app) as conn:
            return await service.get_customer_orders(conn, customer_email, limit)

    @server.tool(annotations=READ_ONLY)
    async def sales_summary(
        ctx: ToolContext,
        start_date: StartDate,
        end_date: EndDate,
        group_by: Annotated[
            GroupBy, Field(description="Period size for the breakdown. Default 'day'.")
        ] = "day",
    ) -> SalesSummary:
        """Revenue, number of orders and average order value (AOV) between two dates, in total
        and per day, week (starting Monday) or month. Cancelled orders are excluded."""
        app = app_context(ctx)
        async with _connection(app) as conn:
            return await service.sales_summary(conn, start_date, end_date, group_by)

    @server.tool(annotations=READ_ONLY)
    async def top_products(
        ctx: ToolContext,
        start_date: StartDate,
        end_date: EndDate,
        limit: Annotated[int, _limit("Default 10.")] = 10,
        by: Annotated[
            RankBy, Field(description="Rank by 'revenue' or units sold ('quantity').")
        ] = "revenue",
    ) -> TopProducts:
        """Best-selling products between two dates, ranked by revenue or by units sold.
        Cancelled orders are excluded."""
        app = app_context(ctx)
        async with _connection(app) as conn:
            return await service.top_products(conn, start_date, end_date, limit, by)

    @server.tool(annotations=READ_ONLY)
    async def low_stock_alert(
        ctx: ToolContext,
        threshold: Annotated[
            int,
            Field(
                ge=0,
                le=service.MAX_STOCK_THRESHOLD,
                description="Products with stock strictly below this value are listed. Default 10.",
            ),
        ] = 10,
    ) -> LowStockReport:
        """Products running low on stock (lowest first) with their units sold and revenue in the
        last 30 days, to decide what to restock."""
        app = app_context(ctx)
        async with _connection(app) as conn:
            return await service.low_stock_alert(conn, threshold)
