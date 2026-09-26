"""Seed job (`python -m ecommerce_mcp.infra.seed`): deterministic fake shop data with embeddings."""

import asyncio
import csv
import logging
import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from importlib.resources import files
from typing import Any

from faker import Faker
from psycopg import AsyncConnection

from ecommerce_mcp.config import Settings, get_settings
from ecommerce_mcp.core.queries import vector_literal
from ecommerce_mcp.infra.db import apply_schema
from ecommerce_mcp.llm.embeddings import create_embedder

logger = logging.getLogger(__name__)

SEED = 42
CUSTOMER_COUNT = 200
ORDER_COUNT = 1000
HISTORY_DAYS = 182
LOW_STOCK_PRODUCTS = 8
FRESH_ORDER_DAYS = 3
STATUS_WEIGHTS = {"delivered": 75, "shipped": 8, "paid": 5, "pending": 4, "cancelled": 8}
FRESH_STATUSES = ("pending", "paid", "shipped")


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    category: str
    description: str
    price: Decimal
    stock: int

    @property
    def embedding_text(self) -> str:
        return f"{self.name}. {self.category}. {self.description}"


@dataclass(frozen=True)
class Customer:
    email: str
    name: str
    city: str
    created_at: datetime


@dataclass(frozen=True)
class Order:
    customer_index: int
    status: str
    created_at: datetime
    items: tuple[tuple[int, int], ...]  # (product index, quantity)


@dataclass(frozen=True)
class Dataset:
    products: list[Product]
    customers: list[Customer]
    orders: list[Order]


def load_catalog() -> list[dict[str, str]]:
    text = files("ecommerce_mcp.infra").joinpath("catalog.csv").read_text(encoding="utf-8")
    return list(csv.DictReader(text.splitlines()))


def _products(rng: random.Random) -> list[Product]:
    catalog = load_catalog()
    low_stock = set(rng.sample(range(len(catalog)), LOW_STOCK_PRODUCTS))
    return [
        Product(
            sku=row["sku"],
            name=row["name"],
            category=row["category"],
            description=row["description"],
            price=Decimal(row["price"]),
            stock=rng.randint(0, 9) if index in low_stock else rng.randint(15, 250),
        )
        for index, row in enumerate(catalog)
    ]


def _customers(fake: Faker, rng: random.Random, now: datetime) -> list[Customer]:
    customers = []
    for index in range(CUSTOMER_COUNT):
        first, last = fake.first_name(), fake.last_name()
        local_part = ".".join(re.sub(r"[^a-z]", "", part.lower()) for part in (first, last))
        customers.append(
            Customer(
                email=f"{local_part}{index}@example.com",
                name=f"{first} {last}",
                city=fake.city(),
                created_at=now - timedelta(days=rng.uniform(HISTORY_DAYS, 3 * HISTORY_DAYS)),
            )
        )
    return customers


def _orders(rng: random.Random, now: datetime, product_count: int) -> list[Order]:
    popularity = [rng.uniform(0.2, 3.0) for _ in range(product_count)]
    orders = []
    for _ in range(ORDER_COUNT):
        created_at = now - timedelta(days=rng.uniform(0, HISTORY_DAYS))
        if now - created_at < timedelta(days=FRESH_ORDER_DAYS):
            status = rng.choice(FRESH_STATUSES)
        else:
            status = rng.choices(list(STATUS_WEIGHTS), weights=list(STATUS_WEIGHTS.values()))[0]
        product_indexes: set[int] = set()
        for _ in range(rng.randint(1, 4)):
            product_indexes.update(rng.choices(range(product_count), weights=popularity))
        items = tuple((index, rng.randint(1, 3)) for index in sorted(product_indexes))
        orders.append(Order(rng.randrange(CUSTOMER_COUNT), status, created_at, items))
    orders.sort(key=lambda order: order.created_at)
    return orders


def generate_dataset(now: datetime, seed: int = SEED) -> Dataset:
    """Same seed and `now` always produce the same data; history spans the last ~6 months."""
    rng = random.Random(seed)
    fake = Faker("en_US")
    fake.seed_instance(seed)
    products = _products(rng)
    customers = _customers(fake, rng, now)
    return Dataset(products, customers, _orders(rng, now, len(products)))


async def write_dataset(
    conn: AsyncConnection[Any], dataset: Dataset, embeddings: list[list[float]]
) -> None:
    """Replaces all shop data. Rows are inserted in list order right after RESTART IDENTITY,
    so the database id of the n-th product/customer/order is n + 1."""
    async with conn.transaction(), conn.cursor() as cur:
        await cur.execute(
            "TRUNCATE order_items, orders, products, customers RESTART IDENTITY CASCADE"
        )
        await cur.executemany(
            "INSERT INTO products (sku, name, description, category, price, stock, embedding)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s::vector)",
            [
                (p.sku, p.name, p.description, p.category, p.price, p.stock, vector_literal(e))
                for p, e in zip(dataset.products, embeddings, strict=True)
            ],
        )
        await cur.executemany(
            "INSERT INTO customers (email, name, city, created_at) VALUES (%s, %s, %s, %s)",
            [(c.email, c.name, c.city, c.created_at) for c in dataset.customers],
        )
        await cur.executemany(
            "INSERT INTO orders (customer_id, status, created_at) VALUES (%s, %s, %s)",
            [(o.customer_index + 1, o.status, o.created_at) for o in dataset.orders],
        )
        await cur.executemany(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price)"
            " VALUES (%s, %s, %s, %s)",
            [
                (order_id, product_index + 1, quantity, dataset.products[product_index].price)
                for order_id, order in enumerate(dataset.orders, start=1)
                for product_index, quantity in order.items
            ],
        )


async def seed_database(settings: Settings, now: datetime) -> Dataset:
    dataset = generate_dataset(now)
    embedder = create_embedder(settings)
    embeddings = embedder.embed_documents([p.embedding_text for p in dataset.products])
    async with await AsyncConnection.connect(settings.database_url) as conn:
        await apply_schema(conn)
        await write_dataset(conn, dataset, embeddings)
    return dataset


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    dataset = asyncio.run(seed_database(get_settings(), datetime.now(UTC)))
    logger.info(
        "Seeded %d products, %d customers, %d orders",
        len(dataset.products),
        len(dataset.customers),
        len(dataset.orders),
    )


if __name__ == "__main__":
    main()
