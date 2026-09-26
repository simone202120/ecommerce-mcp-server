"""Streamlit chat page: `streamlit run src/ecommerce_mcp/ui/app.py` (needs the HTTP server)."""

import asyncio
import logging

import streamlit as st

from ecommerce_mcp.agent import runner
from ecommerce_mcp.config import get_settings
from ecommerce_mcp.ui import components

logger = logging.getLogger(__name__)
settings = get_settings()

st.set_page_config(page_title="Shop Analyst", page_icon=":material/storefront:", layout="wide")


@st.cache_data(ttl=60, show_spinner=False)
def server_tools() -> list[tuple[str, str]] | None:
    """Tool names and descriptions from the MCP server, or None when it is unreachable."""
    try:
        tools = asyncio.run(runner.load_tools(settings))
    except Exception:
        logger.exception("Could not list tools from %s", settings.mcp_url)
        return None
    return [(tool.name, tool.description) for tool in tools]


def sidebar() -> None:
    with st.sidebar:
        st.subheader("MCP server")
        tools = server_tools()
        status = ":green[●] Connected" if tools is not None else ":red[●] Unreachable"
        st.markdown(f"{status}  \n`{settings.mcp_url}`")
        st.caption(f"Model: `{settings.llm_model}`")
        if tools is None:
            st.caption(
                "Start it with `python -m ecommerce_mcp.server --transport streamable-http`."
            )
        for name, description in tools or []:
            with st.expander(name):
                st.caption(description)
        st.divider()
        if st.button("Clear chat", icon=":material/delete:", width="stretch"):
            st.session_state.history = []
            st.rerun()


def ask(question: str) -> None:
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.status("Working on it…", expanded=True) as status:
            st.write("Loading tools from the MCP server and asking the agent…")
            try:
                report = asyncio.run(runner.answer_question(question, settings))
            except Exception:
                logger.exception("Agent run failed")
                status.update(label="Something went wrong", state="error")
                st.error(
                    "The agent could not answer. Check that the MCP server is running at "
                    f"{settings.mcp_url} and that OPENROUTER_API_KEY is set, then try again."
                )
                return
            calls = len(report.result.tool_calls)
            status.update(
                label=f"Answered in {report.result.latency_seconds:.1f} s with {calls} tool calls",
                state="complete",
                expanded=False,
            )
        components.assistant_turn(report)
    st.session_state.history.append((question, report))


def main() -> None:
    st.session_state.setdefault("history", [])
    sidebar()
    st.title("Shop Analyst")
    st.caption(
        "A LangGraph agent answering business questions through read-only MCP tools "
        "over the shop database."
    )

    for question, report in st.session_state.history:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            components.assistant_turn(report)

    clicked = None
    examples = st.empty()
    if not st.session_state.history:
        with examples.container():
            st.markdown("#### Try one of these")
            for column, example in zip(st.columns(3), components.EXAMPLES, strict=True):
                if column.button(example, width="stretch"):
                    clicked = example

    question = st.chat_input("Ask about products, customers, orders or sales") or clicked
    if question:
        examples.empty()
        ask(question)


main()
