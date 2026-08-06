# ищи переменные в файле .env в корне проекта
from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_")

    openai_api_key: SecretStr
    default_model: str = "gpt-5-mini"
    request_timeout: float = 30.0
    max_retries: int = 3
    
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    app_name: str = "llm-service"
    company_name: str = "Acme"
    debug: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 3600
    llm: LLMSettings = Field(default_factory=LLMSettings)

    # chat
    database_url: str = "postgresql+asyncpg://rag:rag@localhost:5432/rag"
    chat_repository: Literal["json", "postgres"] = "json"
    chat_storage_dir: Path = Path("./var/chats")
    chat_context_strategy: Literal["sliding", "hybrid"] = "sliding"
    chat_context_window: int = 10

@lru_cache
def get_settings() -> Settings:
    return Settings()