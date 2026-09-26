"""Agent wiring (prebuilt ReAct loop over MCP tools) and extraction of a run's tool calls."""

import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from ecommerce_mcp.llm.prompts import agent_system_prompt

Agent = CompiledStateGraph[Any, Any, Any, Any]


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]
    result: str = ""


@dataclass(frozen=True)
class AgentAnswer:
    tool_calls: list[ToolCall]
    answer: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_seconds: float = 0.0


def build_agent(model: BaseChatModel, tools: Sequence[BaseTool], today: date) -> Agent:
    return create_agent(model, tools, system_prompt=agent_system_prompt(today))


def summarize_run(messages: Sequence[BaseMessage], latency_seconds: float = 0.0) -> AgentAnswer:
    ai_messages = [m for m in messages if isinstance(m, AIMessage)]
    results = {m.tool_call_id: m.text for m in messages if isinstance(m, ToolMessage)}
    tool_calls = [
        ToolCall(call["name"], call["args"], results.get(call["id"] or "", ""))
        for message in ai_messages
        for call in message.tool_calls
    ]
    usages = [m.usage_metadata for m in ai_messages if m.usage_metadata]
    return AgentAnswer(
        tool_calls=tool_calls,
        answer=ai_messages[-1].text if ai_messages else "",
        input_tokens=sum(u["input_tokens"] for u in usages),
        output_tokens=sum(u["output_tokens"] for u in usages),
        latency_seconds=latency_seconds,
    )


async def ask(
    agent: Agent,
    question: str,
    callbacks: list[BaseCallbackHandler],
    max_steps: int,
) -> AgentAnswer:
    started = time.perf_counter()
    result = await agent.ainvoke(
        {"messages": [HumanMessage(question)]},
        config={"callbacks": callbacks, "recursion_limit": max_steps},
    )
    return summarize_run(result["messages"], time.perf_counter() - started)
