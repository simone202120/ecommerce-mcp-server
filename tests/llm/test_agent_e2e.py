from datetime import UTC, datetime

import pytest
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp.shared.memory import create_connected_server_and_client_session

from ecommerce_mcp.agent.graph import ask, build_agent
from ecommerce_mcp.config import Settings
from ecommerce_mcp.infra.seed import Dataset
from ecommerce_mcp.llm.chat import create_chat_model
from ecommerce_mcp.llm.tracing import tracing
from ecommerce_mcp.server.app import create_server

pytestmark = [pytest.mark.llm, pytest.mark.integration]

DEMO_QUESTION = "Which products are running low and how much did they sell last month?"


async def test_agent_answers_the_demo_question(settings: Settings, dataset: Dataset) -> None:
    if not settings.openrouter_api_key.get_secret_value():
        pytest.skip("OPENROUTER_API_KEY is not set")
    server = create_server(settings)
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        tools = await load_mcp_tools(session)
        agent = build_agent(create_chat_model(settings), tools, datetime.now(UTC).date())
        with tracing(settings) as trace:
            result = await ask(agent, DEMO_QUESTION, trace.callbacks, settings.agent_max_steps)

    called = {call.name for call in result.tool_calls}
    assert "low_stock_alert" in called
    low_stock_names = [p.name for p in dataset.products if p.stock < 10]
    assert any(name.lower() in result.answer.lower() for name in low_stock_names)
