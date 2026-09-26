"""Builds the FastMCP server: lifespan resources (DB pool, embedder), tools and resources."""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from mcp.server.fastmcp import FastMCP

from ecommerce_mcp.config import Settings
from ecommerce_mcp.infra.db import read_only_pool
from ecommerce_mcp.llm.embeddings import create_embedder
from ecommerce_mcp.server.context import AppContext
from ecommerce_mcp.server.resources import register_resources
from ecommerce_mcp.server.tools import register_tools

SERVER_INSTRUCTIONS = (
    "Read-only access to an online shop database (products, customers, orders). "
    "Use search_products to find products by meaning, get_customer_orders for a customer's "
    "history, sales_summary and top_products for sales analytics over a date range, and "
    "low_stock_alert for products that need restocking. Read schema://tables for the data model. "
    "Money amounts are in EUR; dates are YYYY-MM-DD in UTC. Row limits and date ranges are "
    "capped; an invalid argument returns an error message explaining how to fix it."
)

Lifespan = Callable[[FastMCP[AppContext]], AbstractAsyncContextManager[AppContext]]


def database_lifespan(settings: Settings) -> Lifespan:
    @asynccontextmanager
    async def lifespan(_: FastMCP[AppContext]) -> AsyncIterator[AppContext]:
        async with read_only_pool(settings) as pool:
            # Loading the ONNX model takes about a second of CPU: keep it off the event loop.
            embedder = await asyncio.to_thread(create_embedder, settings)
            yield AppContext(pool=pool, embed_query=embedder.embed_query)

    return lifespan


def create_server(settings: Settings, lifespan: Lifespan | None = None) -> FastMCP[AppContext]:
    server = FastMCP(
        "ecommerce",
        instructions=SERVER_INSTRUCTIONS,
        lifespan=lifespan or database_lifespan(settings),
        host=settings.mcp_host,
        port=settings.mcp_port,
    )
    register_tools(server)
    register_resources(server)
    return server
