import re

import pytest

from ecommerce_mcp.core import queries


def test_vector_literal_formats_pgvector_text() -> None:
    assert queries.vector_literal([0.5, -1, 2.25]) == "[0.5,-1.0,2.25]"


def test_vector_literal_empty() -> None:
    assert queries.vector_literal([]) == "[]"


@pytest.mark.parametrize(
    ("by", "first_key"), [("revenue", "revenue DESC"), ("quantity", "units_sold DESC")]
)
def test_top_products_sql_orders_by_requested_metric(by: str, first_key: str) -> None:
    sql = queries.top_products_sql(by)  # type: ignore[arg-type]
    assert f"ORDER BY {first_key}" in sql
    assert "{" not in sql


def test_top_products_sql_rejects_unknown_metric() -> None:
    with pytest.raises(KeyError):
        queries.top_products_sql("price; DROP TABLE products")  # type: ignore[arg-type]


ALL_QUERIES = [
    queries.SEARCH_PRODUCTS,
    queries.FIND_CUSTOMER,
    queries.CUSTOMER_ORDERS,
    queries.SALES_BY_PERIOD,
    queries.top_products_sql("revenue"),
    queries.LOW_STOCK,
]


@pytest.mark.parametrize("sql", ALL_QUERIES)
def test_queries_are_read_only(sql: str) -> None:
    assert sql.lstrip().upper().startswith(("SELECT", "WITH"))
    assert not re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE)\b", sql, re.IGNORECASE)


@pytest.mark.parametrize(
    "sql",
    [
        queries.SEARCH_PRODUCTS,
        queries.CUSTOMER_ORDERS,
        queries.top_products_sql("quantity"),
        queries.LOW_STOCK,
    ],
)
def test_multi_row_queries_are_limited(sql: str) -> None:
    assert "LIMIT %(limit)s" in sql


@pytest.mark.parametrize(
    "sql", [queries.SALES_BY_PERIOD, queries.top_products_sql("revenue"), queries.LOW_STOCK]
)
def test_revenue_queries_exclude_cancelled_orders(sql: str) -> None:
    assert "o.status <> 'cancelled'" in sql
