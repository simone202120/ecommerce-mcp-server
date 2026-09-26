"""MCP resources: a human- and LLM-readable description of the shop tables."""

from mcp.server.fastmcp import FastMCP

from ecommerce_mcp.server.context import AppContext

TABLES_DESCRIPTION = """\
# Shop data model (PostgreSQL, read-only)

## customers
One row per registered customer.
- id: integer primary key
- email: unique, lowercase; used by get_customer_orders
- name, city: text
- created_at: registration time (UTC)

## products
The catalog (about 50 products).
- id: integer primary key
- sku: unique product code, e.g. EL-001
- name, description: text
- category: Electronics, Home & Kitchen, Sports & Outdoors, Books, Clothing,
  Beauty & Personal Care
- price: unit price in EUR
- stock: units currently in the warehouse
- embedding: 384-dim vector of name + category + description, used by search_products

## orders
One row per checkout.
- id: integer primary key
- customer_id: references customers.id
- status: pending | paid | shipped | delivered | cancelled
  (cancelled orders are excluded from every sales figure)
- created_at: order time (UTC)

## order_items
Lines of an order.
- order_id: references orders.id
- product_id: references products.id
- quantity: units bought (> 0)
- unit_price: price paid per unit in EUR
"""


def register_resources(server: FastMCP[AppContext]) -> None:
    @server.resource(
        "schema://tables",
        name="tables",
        description="Tables, columns and business rules of the shop database.",
        mime_type="text/markdown",
    )
    def tables() -> str:
        return TABLES_DESCRIPTION
