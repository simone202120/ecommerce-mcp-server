from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from decimal import Decimal
from typing import Any

import psycopg
import pytest
from mcp.client.session import ClientSession
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent, TextResourceContents
from pydantic import AnyUrl

from ecommerce_mcp.config import Settings
from ecommerce_mcp.server.app import create_server
from ecommerce_mcp.server.context import AppContext
from tests.unit.fakes import FakeConnection, FakePool, fake_embed

ClientFactory = Callable[[FakeConnection], AbstractAsyncContextManager[ClientSession]]

TOOL_NAMES = {
    "search_products",
    "get_customer_orders",
    "sales_summary",
    "top_products",
    "low_stock_alert",
}


class FailingConnection(FakeConnection):
    def cursor(self, row_factory: object) -> Any:
        raise psycopg.OperationalError("connection to server at 10.0.0.5 failed: secret detail")


@pytest.fixture
def client() -> ClientFactory:
    @asynccontextmanager
    async def connect(conn: FakeConnection) -> AsyncIterator[ClientSession]:
        @asynccontextmanager
        async def lifespan(_: FastMCP[AppContext]) -> AsyncIterator[AppContext]:
            yield AppContext(pool=FakePool(conn).as_pool(), embed_query=fake_embed)

        server = create_server(Settings(_env_file=None), lifespan=lifespan)
        async with create_connected_server_and_client_session(server._mcp_server) as session:
            yield session

    return connect


def error_text(result: Any) -> str:
    assert result.isError
    content = result.content[0]
    assert isinstance(content, TextContent)
    return content.text


async def test_lists_the_five_read_only_tools(client: ClientFactory) -> None:
    async with client(FakeConnection()) as session:
        tools = (await session.list_tools()).tools
    assert {tool.name for tool in tools} == TOOL_NAMES
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.description
        assert tool.outputSchema is not None
        assert "ctx" not in tool.inputSchema["properties"]


async def test_tool_schemas_expose_bounds_and_enums(client: ClientFactory) -> None:
    async with client(FakeConnection()) as session:
        tools = {tool.name: tool for tool in (await session.list_tools()).tools}
    search = tools["search_products"].inputSchema
    assert search["required"] == ["query"]
    assert search["properties"]["limit"]["maximum"] == 50
    summary = tools["sales_summary"].inputSchema["properties"]
    assert summary["group_by"]["enum"] == ["day", "week", "month"]
    assert summary["start_date"]["format"] == "date"


async def test_search_products_returns_structured_content(client: ClientFactory) -> None:
    row = {
        "sku": "EL-001",
        "name": "Headphones",
        "category": "Electronics",
        "description": "Noise cancelling",
        "price": Decimal("10.00"),
        "stock": 3,
        "similarity": 0.9,
    }
    async with client(FakeConnection([row])) as session:
        result = await session.call_tool("search_products", {"query": "music", "limit": 1})
    assert not result.isError
    assert result.structuredContent is not None
    assert result.structuredContent["products"][0]["sku"] == "EL-001"


async def test_reversed_date_range_is_a_clear_error(client: ClientFactory) -> None:
    async with client(FakeConnection()) as session:
        result = await session.call_tool(
            "sales_summary", {"start_date": "2026-02-01", "end_date": "2026-01-01"}
        )
    assert "must be on or before end_date" in error_text(result)


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("search_products", {"query": "mug", "limit": 0}),
        ("search_products", {"query": "mug", "limit": 51}),
        ("top_products", {"start_date": "2026-01-01", "end_date": "2026-01-31", "by": "price"}),
        ("sales_summary", {"start_date": "yesterday", "end_date": "2026-01-01"}),
        ("low_stock_alert", {"threshold": -1}),
    ],
)
async def test_schema_violations_are_rejected(
    client: ClientFactory, tool: str, arguments: dict[str, Any]
) -> None:
    conn = FakeConnection()
    async with client(conn) as session:
        result = await session.call_tool(tool, arguments)
    assert result.isError
    assert conn.executed == []


async def test_unknown_customer_is_a_clear_error(client: ClientFactory) -> None:
    async with client(FakeConnection([])) as session:
        result = await session.call_tool(
            "get_customer_orders", {"customer_email": "ghost@example.com"}
        )
    assert "no customer found with email 'ghost@example.com'" in error_text(result)


async def test_database_errors_do_not_leak_details(client: ClientFactory) -> None:
    async with client(FailingConnection()) as session:
        result = await session.call_tool("low_stock_alert", {})
    text = error_text(result)
    assert "the database query failed" in text
    assert "10.0.0.5" not in text


async def test_schema_resource_describes_all_tables(client: ClientFactory) -> None:
    async with client(FakeConnection()) as session:
        resources = (await session.list_resources()).resources
        content = (await session.read_resource(AnyUrl("schema://tables"))).contents[0]
    assert [str(r.uri) for r in resources] == ["schema://tables"]
    assert isinstance(content, TextResourceContents)
    for table in ("customers", "products", "orders", "order_items"):
        assert f"## {table}" in content.text
