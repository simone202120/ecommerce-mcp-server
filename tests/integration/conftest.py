from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from ecommerce_mcp.config import Settings
from ecommerce_mcp.infra.db import read_only_pool
from ecommerce_mcp.infra.seed import Dataset, seed_database
from ecommerce_mcp.llm.embeddings import Embedder, create_embedder


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture(scope="session")
def seed_now() -> datetime:
    return datetime.now(UTC)


@pytest.fixture(scope="session")
async def dataset(settings: Settings, seed_now: datetime) -> Dataset:
    return await seed_database(settings, seed_now)


@pytest.fixture(scope="session")
def embedder(settings: Settings) -> Embedder:
    return create_embedder(settings)


@pytest.fixture(scope="session")
async def pool(
    settings: Settings, dataset: Dataset
) -> AsyncIterator[AsyncConnectionPool[AsyncConnection[Any]]]:
    async with read_only_pool(settings) as opened:
        yield opened


@pytest.fixture
async def conn(
    pool: AsyncConnectionPool[AsyncConnection[Any]],
) -> AsyncIterator[AsyncConnection[Any]]:
    async with pool.connection() as connection:
        yield connection
