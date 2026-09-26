from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg
import pytest
from psycopg import AsyncConnection

from ecommerce_mcp.core import service
from ecommerce_mcp.core.errors import CustomerNotFoundError
from ecommerce_mcp.infra.seed import Dataset, Order
from ecommerce_mcp.llm.embeddings import Embedder

pytestmark = pytest.mark.integration


def counted(orders: list[Order], start: datetime | None = None) -> list[Order]:
    return [
        o for o in orders if o.status != "cancelled" and (start is None or o.created_at >= start)
    ]


def order_revenue(dataset: Dataset, order: Order) -> Decimal:
    return sum(
        (dataset.products[index].price * quantity for index, quantity in order.items), Decimal(0)
    )


async def test_pool_sessions_are_read_only(conn: AsyncConnection[Any]) -> None:
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        await conn.execute("DELETE FROM order_items")


@pytest.mark.parametrize(
    ("query", "expected_sku"),
    [
        ("something to listen to music without noise", "EL-001"),
        ("pan for cooking steak", "HK-002"),
        ("book about saving money and investing", "BK-004"),
        ("protect my skin from the sun", "BT-003"),
    ],
)
async def test_search_products_returns_semantically_related_products(
    conn: AsyncConnection[Any], embedder: Embedder, query: str, expected_sku: str
) -> None:
    result = await service.search_products(conn, embedder.embed_query, query, 3, None)
    assert expected_sku in [p.sku for p in result.products]
    similarities = [p.similarity for p in result.products]
    assert similarities == sorted(similarities, reverse=True)


async def test_search_products_category_filter_is_case_insensitive(
    conn: AsyncConnection[Any], embedder: Embedder
) -> None:
    result = await service.search_products(conn, embedder.embed_query, "gift", 10, "books")
    assert result.products
    assert {p.category for p in result.products} == {"Books"}


async def test_get_customer_orders_matches_seed(
    conn: AsyncConnection[Any], dataset: Dataset
) -> None:
    customer_index, order_count = Counter(o.customer_index for o in dataset.orders).most_common(1)[
        0
    ]
    customer = dataset.customers[customer_index]

    result = await service.get_customer_orders(conn, customer.email.upper(), 50)

    assert result.customer_name == customer.name
    assert len(result.orders) == min(order_count, 50)
    created = [o.created_at for o in result.orders]
    assert created == sorted(created, reverse=True)
    for order in result.orders:
        line_total = sum(line.quantity * line.unit_price for line in order.items)
        assert order.total == pytest.approx(line_total)


async def test_get_customer_orders_unknown_customer(conn: AsyncConnection[Any]) -> None:
    with pytest.raises(CustomerNotFoundError):
        await service.get_customer_orders(conn, "nobody@nowhere.example", 10)


async def test_sales_summary_totals_match_seed(
    conn: AsyncConnection[Any], dataset: Dataset, seed_now: datetime
) -> None:
    start = (seed_now - timedelta(days=400)).date()
    summary = await service.sales_summary(conn, start, seed_now.date(), "month")

    orders = counted(dataset.orders)
    expected_revenue = sum((order_revenue(dataset, o) for o in orders), Decimal(0))
    assert summary.total_orders == len(orders)
    assert summary.total_revenue == pytest.approx(float(expected_revenue))
    assert sum(p.orders for p in summary.periods) == summary.total_orders
    assert 6 <= len(summary.periods) <= 8
    assert all(p.period_start.day == 1 for p in summary.periods)


async def test_sales_summary_by_week_starts_on_monday(
    conn: AsyncConnection[Any], seed_now: datetime
) -> None:
    start = (seed_now - timedelta(days=60)).date()
    summary = await service.sales_summary(conn, start, seed_now.date(), "week")
    assert summary.periods
    assert all(p.period_start.weekday() == 0 for p in summary.periods)


async def test_sales_summary_empty_range(conn: AsyncConnection[Any]) -> None:
    summary = await service.sales_summary(conn, date(2000, 1, 1), date(2000, 1, 31), "day")
    assert summary.total_orders == 0
    assert summary.periods == []


async def test_top_products_by_quantity_matches_seed(
    conn: AsyncConnection[Any], dataset: Dataset, seed_now: datetime
) -> None:
    start = (seed_now - timedelta(days=400)).date()
    result = await service.top_products(conn, start, seed_now.date(), 5, "quantity")

    units: Counter[str] = Counter()
    for order in counted(dataset.orders):
        for index, quantity in order.items:
            units[dataset.products[index].sku] += quantity
    assert len(result.products) == 5
    assert result.products[0].units_sold == units.most_common(1)[0][1]
    assert [p.units_sold for p in result.products] == sorted(
        (p.units_sold for p in result.products), reverse=True
    )


async def test_top_products_by_revenue_is_sorted(
    conn: AsyncConnection[Any], seed_now: datetime
) -> None:
    start = (seed_now - timedelta(days=30)).date()
    result = await service.top_products(conn, start, seed_now.date(), 10, "revenue")
    revenues = [p.revenue for p in result.products]
    assert revenues == sorted(revenues, reverse=True)
    assert [p.rank for p in result.products] == list(range(1, len(revenues) + 1))


async def test_low_stock_alert_matches_seed(
    conn: AsyncConnection[Any], dataset: Dataset, seed_now: datetime
) -> None:
    report = await service.low_stock_alert(conn, 10)

    expected = {p.sku for p in dataset.products if p.stock < 10}
    assert {p.sku for p in report.products} == expected
    recent = counted(dataset.orders, start=seed_now - timedelta(days=30))
    for product in report.products:
        index = next(i for i, p in enumerate(dataset.products) if p.sku == product.sku)
        sold = sum(q for o in recent for i, q in o.items if i == index)
        # The tool's 30-day window starts slightly after the fixture's, never before.
        assert product.units_sold_last_30_days <= sold


async def test_low_stock_alert_zero_threshold_is_empty(conn: AsyncConnection[Any]) -> None:
    report = await service.low_stock_alert(conn, 0)
    assert report.products == []
