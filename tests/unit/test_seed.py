from datetime import UTC, datetime, timedelta

from ecommerce_mcp.infra.seed import (
    CUSTOMER_COUNT,
    FRESH_ORDER_DAYS,
    FRESH_STATUSES,
    HISTORY_DAYS,
    LOW_STOCK_PRODUCTS,
    ORDER_COUNT,
    generate_dataset,
    load_catalog,
)

NOW = datetime(2026, 6, 1, 12, tzinfo=UTC)


def test_catalog_has_about_fifty_unique_products() -> None:
    catalog = load_catalog()
    assert len(catalog) == 50
    assert len({row["sku"] for row in catalog}) == 50
    assert all(row["description"] and row["category"] for row in catalog)


def test_generate_dataset_is_deterministic() -> None:
    assert generate_dataset(NOW) == generate_dataset(NOW)
    assert generate_dataset(NOW) != generate_dataset(NOW, seed=7)


def test_generate_dataset_sizes() -> None:
    dataset = generate_dataset(NOW)
    assert len(dataset.customers) == CUSTOMER_COUNT
    assert len(dataset.orders) == ORDER_COUNT
    assert len({c.email for c in dataset.customers}) == CUSTOMER_COUNT


def test_generate_dataset_has_exactly_the_planned_low_stock_products() -> None:
    dataset = generate_dataset(NOW)
    assert sum(p.stock < 10 for p in dataset.products) == LOW_STOCK_PRODUCTS
    assert all(p.stock >= 0 for p in dataset.products)


def test_orders_span_the_history_window_in_time_order() -> None:
    orders = generate_dataset(NOW).orders
    assert all(NOW - timedelta(days=HISTORY_DAYS) <= o.created_at <= NOW for o in orders)
    assert [o.created_at for o in orders] == sorted(o.created_at for o in orders)


def test_orders_have_distinct_products_with_positive_quantities() -> None:
    dataset = generate_dataset(NOW)
    for order in dataset.orders:
        product_indexes = [index for index, _ in order.items]
        assert 1 <= len(order.items) <= 4
        assert len(set(product_indexes)) == len(product_indexes)
        assert all(0 <= index < len(dataset.products) for index in product_indexes)
        assert all(quantity >= 1 for _, quantity in order.items)
        assert 0 <= order.customer_index < CUSTOMER_COUNT


def test_fresh_orders_are_not_yet_delivered_or_cancelled() -> None:
    fresh = [
        o
        for o in generate_dataset(NOW).orders
        if NOW - o.created_at < timedelta(days=FRESH_ORDER_DAYS)
    ]
    assert fresh
    assert all(o.status in FRESH_STATUSES for o in fresh)
