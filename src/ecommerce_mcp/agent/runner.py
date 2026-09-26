"""Runs one question end to end (MCP tools, LLM, tracing); shared by the CLI and the UI."""

from dataclasses import dataclass
from datetime import UTC, datetime

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from ecommerce_mcp.agent.graph import AgentAnswer, ask, build_agent
from ecommerce_mcp.config import Settings
from ecommerce_mcp.llm.chat import create_chat_model, estimate_cost_usd
from ecommerce_mcp.llm.tracing import tracing


@dataclass(frozen=True)
class RunReport:
    result: AgentAnswer
    cost_usd: float
    trace_url: str | None


async def load_tools(settings: Settings) -> list[BaseTool]:
    client = MultiServerMCPClient(
        {"shop": {"url": settings.mcp_url, "transport": "streamable_http"}}
    )
    return await client.get_tools()


async def answer_question(question: str, settings: Settings) -> RunReport:
    tools = await load_tools(settings)
    agent = build_agent(create_chat_model(settings), tools, datetime.now(UTC).date())
    with tracing(settings) as trace:
        result = await ask(agent, question, trace.callbacks, settings.agent_max_steps)
    cost = estimate_cost_usd(settings, result.input_tokens, result.output_tokens)
    return RunReport(result=result, cost_usd=cost, trace_url=trace.trace_url())
