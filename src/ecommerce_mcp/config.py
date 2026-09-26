"""Application settings loaded from environment variables (and `.env` in local development)."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "google/gemini-3.8-flash"

    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_host: str = "https://cloud.langfuse.com"

    database_url: str = "postgresql://shop:shop@localhost:5432/shop"
    db_pool_size: int = Field(default=5, gt=0)
    db_statement_timeout_ms: int = Field(default=5000, gt=0)

    embedding_model: str = "BAAI/bge-small-en-v1.5"

    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8000
    mcp_url: str = "http://localhost:8000/mcp"

    llm_timeout_seconds: float = 60.0
    agent_max_steps: int = 12

    @property
    def tracing_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
