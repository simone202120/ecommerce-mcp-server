"""CLI: `python -m ecommerce_mcp.agent "question"` asks the agent via the MCP server over HTTP."""

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime

from langchain_mcp_adapters.client import MultiServerMCPClient

from ecommerce_mcp.agent.graph import AgentAnswer, ask, build_agent
from ecommerce_mcp.config import Settings, get_settings
from ecommerce_mcp.llm.chat import create_chat_model
from ecommerce_mcp.llm.tracing import tracing_callbacks


def render(result: AgentAnswer) -> str:
    lines = ["Tool calls:"]
    lines += [
        f"  - {call.name}({json.dumps(call.arguments, ensure_ascii=False)})"
        for call in result.tool_calls
    ] or ["  (none)"]
    lines += ["", "Answer:", result.answer]
    return "\n".join(lines) + "\n"


async def run(question: str, settings: Settings) -> AgentAnswer:
    client = MultiServerMCPClient(
        {"shop": {"url": settings.mcp_url, "transport": "streamable_http"}}
    )
    tools = await client.get_tools()
    agent = build_agent(create_chat_model(settings), tools, datetime.now(UTC).date())
    with tracing_callbacks(settings) as callbacks:
        return await ask(agent, question, callbacks, settings.agent_max_steps)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the shop analyst agent a question.")
    parser.add_argument("question", help='e.g. "Which products are running low?"')
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    result = asyncio.run(run(args.question, get_settings()))
    # The answer is the CLI's output, not a log record.
    sys.stdout.write(render(result))


if __name__ == "__main__":
    main()
