"""Test doubles: database connection and pool, embedding model, tool-calling chat model."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any, cast

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool, StructuredTool
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from pydantic import Field


class FakeCursor:
    def __init__(self, conn: "FakeConnection") -> None:
        self.conn = conn

    async def __aenter__(self) -> "FakeCursor":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def execute(self, query: str, params: dict[str, Any]) -> None:
        self.conn.executed.append((query, params))

    async def fetchall(self) -> list[dict[str, Any]]:
        return self.conn.results.pop(0)


class FakeConnection:
    """Records executed queries and returns one canned result set per execute call."""

    def __init__(self, *results: list[dict[str, Any]]) -> None:
        self.results = list(results)
        self.executed: list[tuple[str, dict[str, Any]]] = []

    def cursor(self, row_factory: object) -> FakeCursor:
        return FakeCursor(self)

    def as_conn(self) -> AsyncConnection[Any]:
        return cast(AsyncConnection[Any], self)


def fake_embed(text: str) -> Sequence[float]:
    return [0.25, 0.5]


class FakePool:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[AsyncConnection[Any]]:
        yield self.conn.as_conn()

    def as_pool(self) -> AsyncConnectionPool[AsyncConnection[Any]]:
        return cast(AsyncConnectionPool[AsyncConnection[Any]], self)


class FakeToolCallingModel(GenericFakeChatModel):
    """Replays scripted AI messages and records the prompts it received."""

    seen: list[list[BaseMessage]] = Field(default_factory=list)

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "FakeToolCallingModel":
        return self

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> Any:
        self.seen.append(list(messages))
        return super()._generate(messages, *args, **kwargs)


def low_stock_alert(threshold: int = 10) -> str:
    """Products running low on stock."""
    return '{"products": [{"sku": "EL-007", "stock": 0, "units_sold_last_30_days": 12}]}'


def make_tools() -> list[BaseTool]:
    return [StructuredTool.from_function(low_stock_alert)]


def scripted_model() -> FakeToolCallingModel:
    return FakeToolCallingModel(
        messages=iter(
            [
                AIMessage(
                    "",
                    tool_calls=[{"name": "low_stock_alert", "args": {"threshold": 5}, "id": "c1"}],
                ),
                AIMessage("EL-007 is out of stock and sold 12 units in the last 30 days."),
            ]
        ),
    )
