"""Agent wiring (prebuilt ReAct loop over MCP tools) and extraction of a run's tool calls."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from ecommerce_mcp.llm.prompts import agent_system_prompt

Agent = CompiledStateGraph[Any, Any, Any, Any]


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class AgentAnswer:
    tool_calls: list[ToolCall]
    answer: str


def build_agent(model: BaseChatModel, tools: Sequence[BaseTool], today: date) -> Agent:
    return create_agent(model, tools, system_prompt=agent_system_prompt(today))


def summarize_run(messages: Sequence[BaseMessage]) -> AgentAnswer:
    ai_messages = [m for m in messages if isinstance(m, AIMessage)]
    tool_calls = [
        ToolCall(call["name"], call["args"])
        for message in ai_messages
        for call in message.tool_calls
    ]
    answer = ai_messages[-1].text if ai_messages else ""
    return AgentAnswer(tool_calls=tool_calls, answer=answer)


async def ask(
    agent: Agent,
    question: str,
    callbacks: list[BaseCallbackHandler],
    max_steps: int,
) -> AgentAnswer:
    result = await agent.ainvoke(
        {"messages": [HumanMessage(question)]},
        config={"callbacks": callbacks, "recursion_limit": max_steps},
    )
    return summarize_run(result["messages"])
