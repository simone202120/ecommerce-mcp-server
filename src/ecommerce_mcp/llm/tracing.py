"""Optional Langfuse tracing: callbacks and a trace link when keys are configured, else nothing."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from langchain_core.callbacks import BaseCallbackHandler
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from ecommerce_mcp.config import Settings


@dataclass
class Tracing:
    callbacks: list[BaseCallbackHandler] = field(default_factory=list)
    client: Langfuse | None = None
    handler: CallbackHandler | None = None

    def trace_url(self) -> str | None:
        if self.client is None or self.handler is None or not self.handler.last_trace_id:
            return None
        return self.client.get_trace_url(trace_id=self.handler.last_trace_id)


@contextmanager
def tracing(settings: Settings) -> Iterator[Tracing]:
    """Yields the callbacks to pass to a run and flushes traces on exit."""
    if not settings.tracing_enabled:
        yield Tracing()
        return
    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        host=settings.langfuse_host,
    )
    handler = CallbackHandler(public_key=settings.langfuse_public_key)
    try:
        yield Tracing(callbacks=[handler], client=client, handler=handler)
    finally:
        # CLI and UI runs are short-lived: send buffered spans right away.
        client.flush()
