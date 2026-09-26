"""Result models returned by the shop tools; they define the structured output MCP clients see."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

GroupBy = Literal["day", "week", "month"]
RankBy = Literal["revenue", "quantity"]


class ProductMatch(BaseModel):
    sku: str
    name: str
    category: str
    description: str
    price: float
    stock: int
    similarity: float


class ProductSearchResult(BaseModel):
    query: str
    category: str | None
    products: list[ProductMatch]


class OrderLine(BaseModel):
    sku: str
    product: str
    quantity: int
    unit_price: float


class Order(BaseModel):
    order_id: int
    status: str
    created_at: datetime
    total: float
    items: list[OrderLine]


class CustomerOrders(BaseModel):
    customer_email: str
    customer_name: str
    orders: list[Order]


class SalesPeriod(BaseModel):
    period_start: date
    orders: int
    revenue: float
    average_order_value: float


class SalesSummary(BaseModel):
    start_date: date
    end_date: date
    group_by: GroupBy
    total_orders: int
    total_revenue: float
    average_order_value: float
    periods: list[SalesPeriod]


class TopProduct(BaseModel):
    rank: int
    sku: str
    name: str
    category: str
    units_sold: int
    revenue: float


class TopProducts(BaseModel):
    start_date: date
    end_date: date
    ranked_by: RankBy
    products: list[TopProduct]


class LowStockProduct(BaseModel):
    sku: str
    name: str
    category: str
    stock: int
    price: float
    units_sold_last_30_days: int
    revenue_last_30_days: float


class LowStockReport(BaseModel):
    threshold: int
    products: list[LowStockProduct]
