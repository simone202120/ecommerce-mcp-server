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
