from typing import Any

import pytest
from langchain_openai import ChatOpenAI

from ecommerce_mcp.config import Settings
from ecommerce_mcp.llm import tracing
from ecommerce_mcp.llm.chat import create_chat_model


def test_chat_model_targets_openrouter_with_configured_model() -> None:
    settings = Settings(_env_file=None, openrouter_api_key="sk-test", llm_model="some/model")
    model = create_chat_model(settings)
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "some/model"
    assert model.openai_api_base == settings.openrouter_base_url
    assert model.temperature == 0


def test_tracing_disabled_without_keys_yields_no_callbacks() -> None:
    settings = Settings(_env_file=None, langfuse_public_key="", langfuse_secret_key="")
    with tracing.tracing_callbacks(settings) as callbacks:
        assert callbacks == []


def test_tracing_enabled_yields_handler_and_flushes(monkeypatch: pytest.MonkeyPatch) -> None:
    flushed: list[bool] = []

    class FakeLangfuse:
        def __init__(self, **kwargs: Any) -> None:
            assert kwargs["secret_key"] == "sk"

        def flush(self) -> None:
            flushed.append(True)

    monkeypatch.setattr(tracing, "Langfuse", FakeLangfuse)
    monkeypatch.setattr(tracing, "CallbackHandler", lambda public_key: f"handler:{public_key}")
    settings = Settings(_env_file=None, langfuse_public_key="pk", langfuse_secret_key="sk")

    with tracing.tracing_callbacks(settings) as callbacks:
        assert callbacks == ["handler:pk"]
        assert flushed == []
    assert flushed == [True]
