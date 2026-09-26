"""The single place where the chat LLM (OpenRouter, OpenAI-compatible API) is created."""

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from ecommerce_mcp.config import Settings


def create_chat_model(settings: Settings) -> BaseChatModel:
    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        temperature=0,
        timeout=settings.llm_timeout_seconds,
    )


def estimate_cost_usd(settings: Settings, input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * settings.llm_input_usd_per_mtok
        + output_tokens * settings.llm_output_usd_per_mtok
    ) / 1_000_000
