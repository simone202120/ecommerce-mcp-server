from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

import pytest
from psycopg import AsyncConnection

from ecommerce_mcp.core import queries, service
from ecommerce_mcp.core.errors import CustomerNotFoundError, InvalidInputError


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


PRODUCT_ROW = {
    "sku": "EL-001",
    "name": "Wireless Headphones",
    "category": "Electronics",
    "description": "Noise cancelling",
    "price": Decimal("129.90"),
    "stock": 4,
    "similarity": 0.812345,
}


async def test_search_products_embeds_cleaned_query_and_formats_rows() -> None:
    conn = FakeConnection([PRODUCT_ROW])
    embedded: list[str] = []

    def embed(text: str) -> Sequence[float]:
        embedded.append(text)
        return [0.25, 0.5]

    result = await service.search_products(conn.as_conn(), embed, "  noise  cancelling ", 5, " ")

    assert embedded == ["noise cancelling"]
    sql, params = conn.executed[0]
    assert sql == queries.SEARCH_PRODUCTS
    assert params == {"embedding": "[0.25,0.5]", "category": None, "limit": 5}
    assert result.query == "noise cancelling"
    assert result.products[0].price == 129.9
    assert result.products[0].similarity == 0.8123


async def test_search_products_rejects_blank_query_without_touching_db() -> None:
    conn = FakeConnection()
    with pytest.raises(InvalidInputError):
        await service.search_products(conn.as_conn(), fake_embed, "   ", 5, None)
    assert conn.executed == []


async def test_search_products_passes_category_filter() -> None:
    conn = FakeConnection([])
    result = await service.search_products(conn.as_conn(), fake_embed, "mug", 3, "Home")
    assert conn.executed[0][1]["category"] == "Home"
    assert result.products == []


async def test_get_customer_orders_returns_orders_with_items() -> None:
    customer = {"id": 7, "email": "jane@example.com", "name": "Jane Doe"}
    order = {
        "order_id": 42,
        "status": "delivered",
        "created_at": datetime(2026, 5, 1, 10, tzinfo=UTC),
        "total": Decimal("59.97"),
        "items": [{"sku": "HK-001", "product": "Mug", "quantity": 3, "unit_price": 19.990001}],
    }
    conn = FakeConnection([customer], [order])

    result = await service.get_customer_orders(conn.as_conn(), " Jane@Example.com", 10)

    assert conn.executed[0][1] == {"email": "jane@example.com"}
    assert conn.executed[1][1] == {"customer_id": 7, "limit": 10}
    assert result.customer_name == "Jane Doe"
    assert result.orders[0].total == 59.97
    assert result.orders[0].items[0].quantity == 3
    assert result.orders[0].items[0].unit_price == 19.99


async def test_get_customer_orders_unknown_email_raises() -> None:
    conn = FakeConnection([])
    with pytest.raises(CustomerNotFoundError, match=r"nobody@example\.com"):
        await service.get_customer_orders(conn.as_conn(), "nobody@example.com", 10)
    assert len(conn.executed) == 1


async def test_get_customer_orders_invalid_email_raises() -> None:
    conn = FakeConnection()
    with pytest.raises(InvalidInputError):
        await service.get_customer_orders(conn.as_conn(), "not-an-email", 10)


def test_summarize_sales_computes_totals_and_average_order_value() -> None:
    rows = [
        {"period_start": date(2026, 1, 1), "orders": 2, "revenue": Decimal("100.00")},
        {"period_start": date(2026, 2, 1), "orders": 1, "revenue": Decimal("50.01")},
    ]
    summary = service.summarize_sales(rows, date(2026, 1, 1), date(2026, 2, 28), "month")
    assert summary.total_orders == 3
    assert summary.total_revenue == 150.01
    assert summary.average_order_value == 50.0
    assert summary.periods[0].average_order_value == 50.0
    assert summary.periods[1].revenue == 50.01


def test_summarize_sales_with_no_orders_is_zero() -> None:
    summary = service.summarize_sales([], date(2026, 1, 1), date(2026, 1, 2), "day")
    assert summary.total_orders == 0
    assert summary.total_revenue == 0
    assert summary.average_order_value == 0
    assert summary.periods == []


async def test_sales_summary_queries_half_open_range() -> None:
    conn = FakeConnection([])
    await service.sales_summary(conn.as_conn(), date(2026, 1, 1), date(2026, 1, 31), "week")
    params = conn.executed[0][1]
    assert params["group_by"] == "week"
    assert params["start"] == datetime(2026, 1, 1, tzinfo=UTC)
    assert params["end"] == datetime(2026, 2, 1, tzinfo=UTC)


async def test_sales_summary_rejects_reversed_dates_without_touching_db() -> None:
    conn = FakeConnection()
    with pytest.raises(InvalidInputError):
        await service.sales_summary(conn.as_conn(), date(2026, 2, 1), date(2026, 1, 1), "day")
    assert conn.executed == []


async def test_top_products_ranks_rows_in_order() -> None:
    rows = [
        {"sku": "A", "name": "A", "category": "X", "units_sold": 5, "revenue": Decimal("10")},
        {"sku": "B", "name": "B", "category": "X", "units_sold": 9, "revenue": Decimal("9.5")},
    ]
    conn = FakeConnection(rows)
    result = await service.top_products(
        conn.as_conn(), date(2026, 1, 1), date(2026, 1, 31), 2, "revenue"
    )
    assert conn.executed[0][0] == queries.top_products_sql("revenue")
    assert conn.executed[0][1]["limit"] == 2
    assert [(p.rank, p.sku) for p in result.products] == [(1, "A"), (2, "B")]
    assert result.ranked_by == "revenue"


async def test_low_stock_alert_uses_last_30_days_and_row_cap() -> None:
    row = {
        "sku": "SP-003",
        "name": "Yoga Mat",
        "category": "Sports",
        "stock": 2,
        "price": Decimal("25.00"),
        "units_sold_last_30_days": 11,
        "revenue_last_30_days": Decimal("275.00"),
    }
    conn = FakeConnection([row])
    before = datetime.now(UTC)

    report = await service.low_stock_alert(conn.as_conn(), 10)

    params = conn.executed[0][1]
    assert params["threshold"] == 10
    assert params["limit"] == service.LOW_STOCK_MAX_ROWS
    expected_since = before - timedelta(days=30)
    assert abs((params["since"] - expected_since).total_seconds()) < 5
    assert report.threshold == 10
    assert report.products[0].revenue_last_30_days == 275.0
