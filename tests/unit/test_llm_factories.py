from typing import Any

import pytest
from langchain_openai import ChatOpenAI

from ecommerce_mcp.config import Settings
from ecommerce_mcp.llm import tracing
from ecommerce_mcp.llm.chat import create_chat_model, estimate_cost_usd


def test_chat_model_targets_openrouter_with_configured_model() -> None:
    settings = Settings(_env_file=None, openrouter_api_key="sk-test", llm_model="some/model")
    model = create_chat_model(settings)
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "some/model"
    assert model.openai_api_base == settings.openrouter_base_url
    assert model.temperature == 0


def test_estimate_cost_uses_configured_prices_per_million_tokens() -> None:
    settings = Settings(_env_file=None, llm_input_usd_per_mtok=1.0, llm_output_usd_per_mtok=4.0)
    assert estimate_cost_usd(settings, 500_000, 250_000) == pytest.approx(1.5)


def test_tracing_disabled_without_keys_yields_no_callbacks() -> None:
    settings = Settings(_env_file=None, langfuse_public_key="", langfuse_secret_key="")
    with tracing.tracing(settings) as trace:
        assert trace.callbacks == []
    assert trace.trace_url() is None


def test_tracing_enabled_yields_handler_flushes_and_links_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flushed: list[bool] = []

    class FakeLangfuse:
        def __init__(self, **kwargs: Any) -> None:
            assert kwargs["secret_key"] == "sk"

        def flush(self) -> None:
            flushed.append(True)

        def get_trace_url(self, trace_id: str) -> str:
            return f"https://langfuse/traces/{trace_id}"

    class FakeHandler:
        def __init__(self, public_key: str) -> None:
            self.last_trace_id: str | None = None

    monkeypatch.setattr(tracing, "Langfuse", FakeLangfuse)
    monkeypatch.setattr(tracing, "CallbackHandler", FakeHandler)
    settings = Settings(_env_file=None, langfuse_public_key="pk", langfuse_secret_key="sk")

    with tracing.tracing(settings) as trace:
        assert len(trace.callbacks) == 1
        assert trace.trace_url() is None
        trace.callbacks[0].last_trace_id = "abc"  # type: ignore[attr-defined]
        assert flushed == []
    assert flushed == [True]
    assert trace.trace_url() == "https://langfuse/traces/abc"
