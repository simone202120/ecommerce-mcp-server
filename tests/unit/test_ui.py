import json
from pathlib import Path
from typing import Any

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from ecommerce_mcp.agent import runner
from ecommerce_mcp.agent.graph import AgentAnswer, ToolCall
from ecommerce_mcp.agent.runner import RunReport
from ecommerce_mcp.config import Settings
from ecommerce_mcp.ui import components
from tests.unit.fakes import make_tools

APP = str(Path(components.__file__).with_name("app.py"))

SALES_RESULT = json.dumps(
    {
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
        "group_by": "week",
        "total_orders": 12,
        "total_revenue": 1234.5,
        "average_order_value": 102.88,
        "periods": [
            {
                "period_start": "2026-05-04",
                "orders": 12,
                "revenue": 1234.5,
                "average_order_value": 1,
            }
        ],
    }
)


@pytest.fixture(autouse=True)
def fresh_cache() -> None:
    st.cache_data.clear()


@pytest.fixture
def connected(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_load_tools(settings: Settings) -> Any:
        return make_tools()

    monkeypatch.setattr(runner, "load_tools", fake_load_tools)


def run_app() -> AppTest:
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    assert not app.exception
    return app


def test_empty_state_shows_three_examples_and_tools(connected: None) -> None:
    app = run_app()
    assert [b.label for b in app.main.button] == list(components.EXAMPLES)
    sidebar_text = " ".join(m.value for m in app.sidebar.markdown)
    assert "Connected" in sidebar_text
    assert "low_stock_alert" in [e.label for e in app.sidebar.expander]


def test_unreachable_server_is_shown_in_sidebar(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_load_tools(settings: Settings) -> Any:
        raise ConnectionError("refused")

    monkeypatch.setattr(runner, "load_tools", failing_load_tools)
    app = run_app()
    assert "Unreachable" in " ".join(m.value for m in app.sidebar.markdown)


def test_example_click_runs_agent_and_renders_answer(
    connected: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_answer(question: str, settings: Settings) -> RunReport:
        answer = AgentAnswer(
            [ToolCall("sales_summary", {"group_by": "week"}, SALES_RESULT)],
            f"Revenue was €1,234.50 for: {question}",
            input_tokens=900,
            output_tokens=60,
            latency_seconds=2.0,
        )
        return RunReport(answer, cost_usd=0.0004, trace_url=None)

    monkeypatch.setattr(runner, "answer_question", fake_answer)
    app = run_app()
    app.main.button[0].click().run()

    assert not app.exception
    markdown = " ".join(m.value for m in app.markdown)
    assert "Revenue was €1,234.50" in markdown
    assert "sales_summary" in " ".join(e.label for e in app.expander)
    metrics = {m.label: m.value for m in app.metric}
    assert metrics["Revenue"] == "€1,234.50"
    assert metrics["Tool calls"] == "1"
    assert metrics["Est. cost"] == "$0.0004"
    assert not app.main.button  # examples disappear once the chat has history


def test_agent_failure_shows_friendly_error(
    connected: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing_answer(question: str, settings: Settings) -> RunReport:
        raise RuntimeError("boom")

    monkeypatch.setattr(runner, "answer_question", failing_answer)
    app = run_app()
    app.main.button[1].click().run()

    assert not app.exception
    assert "could not answer" in app.error[0].value
    assert "boom" not in app.error[0].value


@pytest.mark.parametrize(
    ("text", "expected"),
    [('{"a": 1}', {"a": 1}), ("Error executing tool", None), ("[1, 2]", None)],
)
def test_parse_result(text: str, expected: dict[str, Any] | None) -> None:
    assert components.parse_result(text) == expected
