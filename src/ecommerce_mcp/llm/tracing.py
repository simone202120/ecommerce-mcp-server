"""Optional Langfuse tracing: callbacks when keys are configured, nothing otherwise."""

from collections.abc import Iterator
from contextlib import contextmanager

from langchain_core.callbacks import BaseCallbackHandler
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from ecommerce_mcp.config import Settings


@contextmanager
def tracing_callbacks(settings: Settings) -> Iterator[list[BaseCallbackHandler]]:
    """Yields the LangChain callbacks to pass to a run and flushes traces on exit."""
    if not settings.tracing_enabled:
        yield []
        return
    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        host=settings.langfuse_host,
    )
    try:
        yield [CallbackHandler(public_key=settings.langfuse_public_key)]
    finally:
        # A CLI run is short-lived: send buffered spans before the process exits.
        client.flush()
