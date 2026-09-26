from datetime import datetime, timedelta
from typing import Any

import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session

from ecommerce_mcp.config import Settings
from ecommerce_mcp.infra.seed import Dataset
from ecommerce_mcp.server.app import create_server

pytestmark = pytest.mark.integration


async def call(session: ClientSession, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = await session.call_tool(tool, arguments)
    assert not result.isError, result.content
    assert result.structuredContent is not None
    return result.structuredContent


async def test_every_tool_answers_on_seeded_data(
    settings: Settings, dataset: Dataset, seed_now: datetime
) -> None:
    # The client runs inside the test: anyio task groups cannot span fixture setup and teardown.
    server = create_server(settings)
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        await assert_every_tool_answers(session, dataset, seed_now)


async def assert_every_tool_answers(
    session: ClientSession, dataset: Dataset, seed_now: datetime
) -> None:
    tools = {tool.name for tool in (await session.list_tools()).tools}
    assert len(tools) == 5
    last_month = {
        "start_date": (seed_now - timedelta(days=30)).date().isoformat(),
        "end_date": seed_now.date().isoformat(),
    }

    search = await call(session, "search_products", {"query": "warm clothes for winter"})
    assert {"CL-001", "CL-007"} & {p["sku"] for p in search["products"]}

    email = dataset.customers[dataset.orders[-1].customer_index].email
    orders = await call(session, "get_customer_orders", {"customer_email": email, "limit": 3})
    assert 1 <= len(orders["orders"]) <= 3

    summary = await call(session, "sales_summary", {**last_month, "group_by": "week"})
    assert summary["total_orders"] > 0
    assert summary["total_revenue"] > 0

    top = await call(session, "top_products", {**last_month, "limit": 3, "by": "quantity"})
    assert len(top["products"]) == 3

    low = await call(session, "low_stock_alert", {"threshold": 10})
    assert {p["sku"] for p in low["products"]} == {p.sku for p in dataset.products if p.stock < 10}
