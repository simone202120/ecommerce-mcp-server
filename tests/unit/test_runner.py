from typing import Any

import pytest
from langchain_core.tools import BaseTool

from ecommerce_mcp.agent import runner
from ecommerce_mcp.config import Settings
from tests.unit.fakes import make_tools, scripted_model


async def test_answer_question_runs_agent_and_estimates_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_load_tools(settings: Settings) -> list[BaseTool]:
        return make_tools()

    def fake_model(settings: Settings) -> Any:
        return scripted_model()

    monkeypatch.setattr(runner, "load_tools", fake_load_tools)
    monkeypatch.setattr(runner, "create_chat_model", fake_model)
    settings = Settings(_env_file=None, langfuse_public_key="", langfuse_secret_key="")

    report = await runner.answer_question("Which products are running low?", settings)

    assert [call.name for call in report.result.tool_calls] == ["low_stock_alert"]
    assert "EL-007" in report.result.answer
    assert report.cost_usd >= 0
    assert report.trace_url is None
