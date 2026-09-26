"""Rendering helpers for the chat page: tool cards, per-tool result previews and run metrics."""

import json
import logging
from collections.abc import Callable
from typing import Any

import pandas as pd
import streamlit as st

from ecommerce_mcp.agent.graph import ToolCall
from ecommerce_mcp.agent.runner import RunReport

logger = logging.getLogger(__name__)

EXAMPLES = (
    "Which products are running low and how did they sell last month?",
    "Top 5 products by revenue this quarter",
    "Find products similar to 'wireless headphones'",
)


def parse_result(text: str) -> dict[str, Any] | None:
    """Tool results are JSON objects; errors and anything else come back as plain text."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _table(rows: list[dict[str, Any]], columns: list[str]) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows)[columns], hide_index=True, width="stretch")
    else:
        st.caption("No rows.")


def _search(data: dict[str, Any]) -> None:
    _table(data["products"], ["name", "category", "price", "stock", "similarity"])


def _orders(data: dict[str, Any]) -> None:
    st.metric("Orders shown", len(data["orders"]), help=data["customer_name"])
    rows = [{**o, "items": len(o["items"])} for o in data["orders"]]
    _table(rows, ["order_id", "created_at", "status", "items", "total"])


def _sales(data: dict[str, Any]) -> None:
    left, middle, right = st.columns(3)
    left.metric("Revenue", f"€{data['total_revenue']:,.2f}")
    middle.metric("Orders", data["total_orders"])
    right.metric("Avg order value", f"€{data['average_order_value']:,.2f}")
    if data["periods"]:
        frame = pd.DataFrame(data["periods"]).set_index("period_start")
        st.bar_chart(frame["revenue"], height=220)


def _top(data: dict[str, Any]) -> None:
    metric = "revenue" if data["ranked_by"] == "revenue" else "units_sold"
    if data["products"]:
        frame = pd.DataFrame(data["products"]).set_index("name")
        st.bar_chart(frame[metric], horizontal=True, height=220)
    else:
        st.caption("No sales in this period.")


def _low_stock(data: dict[str, Any]) -> None:
    columns = ["name", "stock", "units_sold_last_30_days", "revenue_last_30_days"]
    _table(data["products"], columns)


CHART_TOOLS = {"sales_summary", "top_products"}

PREVIEWS: dict[str, Callable[[dict[str, Any]], None]] = {
    "search_products": _search,
    "get_customer_orders": _orders,
    "sales_summary": _sales,
    "top_products": _top,
    "low_stock_alert": _low_stock,
}


def tool_card(call: ToolCall) -> None:
    arguments = ", ".join(f"{k}={v!r}" for k, v in call.arguments.items())
    data = parse_result(call.result)
    preview = PREVIEWS.get(call.name)
    label = f":material/build: **{call.name}** ({arguments or 'no arguments'})"
    # Charts carry the numbers of the answer, so those cards start open.
    with st.expander(label, expanded=call.name in CHART_TOOLS):
        if data is None or preview is None:
            st.caption(call.result[:300] or "No result.")
            return
        preview_tab, raw_tab = st.tabs(["Preview", "Raw response"])
        with preview_tab:
            try:
                preview(data)
            except (KeyError, TypeError, ValueError):
                logger.exception("Unexpected %s result shape", call.name)
                st.caption("No preview for this result; see the raw response.")
        with raw_tab:
            st.json(data, expanded=False)


def run_metrics(report: RunReport) -> None:
    result = report.result
    cols = st.columns(4)
    cols[0].metric("Latency", f"{result.latency_seconds:.1f} s")
    cols[1].metric("Tokens", f"{result.input_tokens + result.output_tokens:,}")
    cols[2].metric("Est. cost", f"${report.cost_usd:.4f}")
    cols[3].metric("Tool calls", len(result.tool_calls))
    if report.trace_url:
        st.link_button("Open Langfuse trace", report.trace_url)


def assistant_turn(report: RunReport) -> None:
    for call in report.result.tool_calls:
        tool_card(call)
    st.markdown(report.result.answer)
    run_metrics(report)
