"""Test doubles for the database connection pool and the embedding model."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any, cast

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool


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
