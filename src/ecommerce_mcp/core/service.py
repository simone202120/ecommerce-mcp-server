"""Tool use cases: validate arguments, run the read-only queries and shape the results."""

import asyncio
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from ecommerce_mcp.core import queries
from ecommerce_mcp.core.errors import CustomerNotFoundError
from ecommerce_mcp.core.models import (
    CustomerOrders,
    GroupBy,
    LowStockProduct,
    LowStockReport,
    Order,
    ProductMatch,
    ProductSearchResult,
    RankBy,
    SalesPeriod,
    SalesSummary,
    TopProduct,
    TopProducts,
)
from ecommerce_mcp.core.validation import (
    date_range_bounds,
    normalize_category,
    normalize_email,
    normalize_query,
)

EmbedQuery = Callable[[str], Sequence[float]]
Row = dict[str, Any]

LOW_STOCK_MAX_ROWS = 100
RECENT_SALES_DAYS = 30


async def _fetch_all(
    conn: AsyncConnection[Any], query: str, params: Mapping[str, object]
) -> list[Row]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, params)
        return await cur.fetchall()


def _money(value: Decimal | float) -> float:
    return round(float(value), 2)


def _average(total: Decimal | float, count: int) -> float:
    return _money(Decimal(total) / count) if count else 0.0


async def search_products(
    conn: AsyncConnection[Any],
    embed_query: EmbedQuery,
    query: str,
    limit: int,
    category: str | None,
) -> ProductSearchResult:
    cleaned_query = normalize_query(query)
    cleaned_category = normalize_category(category)
    # FastEmbed inference is CPU-bound and synchronous: keep it off the event loop.
    embedding = await asyncio.to_thread(embed_query, cleaned_query)
    rows = await _fetch_all(
        conn,
        queries.SEARCH_PRODUCTS,
        {
            "embedding": queries.vector_literal(embedding),
            "category": cleaned_category,
            "limit": limit,
        },
    )
    products = [
        ProductMatch.model_validate(
            {**row, "price": _money(row["price"]), "similarity": round(row["similarity"], 4)}
        )
        for row in rows
    ]
    return ProductSearchResult(query=cleaned_query, category=cleaned_category, products=products)


async def get_customer_orders(
    conn: AsyncConnection[Any], customer_email: str, limit: int
) -> CustomerOrders:
    email = normalize_email(customer_email)
    customers = await _fetch_all(conn, queries.FIND_CUSTOMER, {"email": email})
    if not customers:
        raise CustomerNotFoundError(f"no customer found with email '{email}'")
    customer = customers[0]
    rows = await _fetch_all(
        conn, queries.CUSTOMER_ORDERS, {"customer_id": customer["id"], "limit": limit}
    )
    orders = [
        Order.model_validate(
            {
                **row,
                "total": _money(row["total"]),
                "items": [{**i, "unit_price": _money(i["unit_price"])} for i in row["items"]],
            }
        )
        for row in rows
    ]
    return CustomerOrders(
        customer_email=customer["email"], customer_name=customer["name"], orders=orders
    )


def summarize_sales(
    rows: Sequence[Row], start_date: date, end_date: date, group_by: GroupBy
) -> SalesSummary:
    periods = [
        SalesPeriod(
            period_start=row["period_start"],
            orders=row["orders"],
            revenue=_money(row["revenue"]),
            average_order_value=_average(row["revenue"], row["orders"]),
        )
        for row in rows
    ]
    total_orders = sum(int(row["orders"]) for row in rows)
    total_revenue = sum((Decimal(row["revenue"]) for row in rows), Decimal(0))
    return SalesSummary(
        start_date=start_date,
        end_date=end_date,
        group_by=group_by,
        total_orders=total_orders,
        total_revenue=_money(total_revenue),
        average_order_value=_average(total_revenue, total_orders),
        periods=periods,
    )


async def sales_summary(
    conn: AsyncConnection[Any], start_date: date, end_date: date, group_by: GroupBy
) -> SalesSummary:
    start, end = date_range_bounds(start_date, end_date)
    rows = await _fetch_all(
        conn, queries.SALES_BY_PERIOD, {"group_by": group_by, "start": start, "end": end}
    )
    return summarize_sales(rows, start_date, end_date, group_by)


async def top_products(
    conn: AsyncConnection[Any], start_date: date, end_date: date, limit: int, by: RankBy
) -> TopProducts:
    start, end = date_range_bounds(start_date, end_date)
    rows = await _fetch_all(
        conn, queries.top_products_sql(by), {"start": start, "end": end, "limit": limit}
    )
    products = [
        TopProduct.model_validate({**row, "rank": rank, "revenue": _money(row["revenue"])})
        for rank, row in enumerate(rows, start=1)
    ]
    return TopProducts(start_date=start_date, end_date=end_date, ranked_by=by, products=products)


async def low_stock_alert(conn: AsyncConnection[Any], threshold: int) -> LowStockReport:
    since = datetime.now(UTC) - timedelta(days=RECENT_SALES_DAYS)
    rows = await _fetch_all(
        conn,
        queries.LOW_STOCK,
        {"threshold": threshold, "since": since, "limit": LOW_STOCK_MAX_ROWS},
    )
    products = [
        LowStockProduct.model_validate(
            {
                **row,
                "price": _money(row["price"]),
                "revenue_last_30_days": _money(row["revenue_last_30_days"]),
            }
        )
        for row in rows
    ]
    return LowStockReport(threshold=threshold, products=products)
