"""Parameterized read-only SQL for every tool. Revenue always excludes cancelled orders."""

from collections.abc import Sequence

from ecommerce_mcp.core.models import RankBy

SEARCH_PRODUCTS = """
SELECT sku, name, category, description, price, stock,
       1 - (embedding <=> %(embedding)s::vector) AS similarity
FROM products
WHERE embedding IS NOT NULL
  AND (%(category)s::text IS NULL OR lower(category) = lower(%(category)s::text))
ORDER BY embedding <=> %(embedding)s::vector
LIMIT %(limit)s
"""

FIND_CUSTOMER = """
SELECT id, email, name FROM customers WHERE lower(email) = %(email)s
"""

CUSTOMER_ORDERS = """
SELECT o.id AS order_id, o.status, o.created_at,
       sum(oi.quantity * oi.unit_price) AS total,
       json_agg(json_build_object(
           'sku', p.sku, 'product', p.name,
           'quantity', oi.quantity, 'unit_price', oi.unit_price
       ) ORDER BY oi.id) AS items
FROM orders o
JOIN order_items oi ON oi.order_id = o.id
JOIN products p ON p.id = oi.product_id
WHERE o.customer_id = %(customer_id)s
GROUP BY o.id
ORDER BY o.created_at DESC, o.id DESC
LIMIT %(limit)s
"""

SALES_BY_PERIOD = """
WITH order_totals AS (
    SELECT o.id,
           date_trunc(%(group_by)s, o.created_at AT TIME ZONE 'UTC')::date AS period_start,
           sum(oi.quantity * oi.unit_price) AS total
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.id
    WHERE o.status <> 'cancelled' AND o.created_at >= %(start)s AND o.created_at < %(end)s
    GROUP BY o.id, period_start
)
SELECT period_start, count(*) AS orders, sum(total) AS revenue
FROM order_totals
GROUP BY period_start
ORDER BY period_start
"""

_TOP_PRODUCTS = """
SELECT p.sku, p.name, p.category,
       sum(oi.quantity) AS units_sold,
       sum(oi.quantity * oi.unit_price) AS revenue
FROM order_items oi
JOIN orders o ON o.id = oi.order_id
JOIN products p ON p.id = oi.product_id
WHERE o.status <> 'cancelled' AND o.created_at >= %(start)s AND o.created_at < %(end)s
GROUP BY p.id
ORDER BY {order}, p.name
LIMIT %(limit)s
"""

_TOP_PRODUCTS_ORDER: dict[RankBy, str] = {
    "revenue": "revenue DESC, units_sold DESC",
    "quantity": "units_sold DESC, revenue DESC",
}

LOW_STOCK = """
WITH recent_sales AS (
    SELECT oi.product_id,
           sum(oi.quantity) AS units,
           sum(oi.quantity * oi.unit_price) AS revenue
    FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
    WHERE o.status <> 'cancelled' AND o.created_at >= %(since)s
    GROUP BY oi.product_id
)
SELECT p.sku, p.name, p.category, p.stock, p.price,
       coalesce(r.units, 0) AS units_sold_last_30_days,
       coalesce(r.revenue, 0) AS revenue_last_30_days
FROM products p
LEFT JOIN recent_sales r ON r.product_id = p.id
WHERE p.stock < %(threshold)s
ORDER BY p.stock, p.name
LIMIT %(limit)s
"""


def top_products_sql(by: RankBy) -> str:
    # The ORDER BY column cannot be a bind parameter, so it comes from a fixed whitelist.
    return _TOP_PRODUCTS.format(order=_TOP_PRODUCTS_ORDER[by])


def vector_literal(values: Sequence[float]) -> str:
    """Formats an embedding as a pgvector text literal, e.g. `[0.1,0.2]`."""
    return "[" + ",".join(repr(float(v)) for v in values) + "]"
