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
    embedding_model: str = "text-embedding-3-small"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "documents"
    embedding_dim: int = 1536
    llm: LLMSettings = Field(default_factory=LLMSettings)

    # chat
    database_url: str = "postgresql+asyncpg://rag:rag@localhost:5432/rag"
    chat_repository: Literal["json", "postgres"] = "json"
    chat_storage_dir: Path = Path("./var/chats")
    chat_context_strategy: Literal["sliding", "hybrid"] = "sliding"
    chat_context_window: int = 10
    admin_token: SecretStr = SecretStr("change-me-admin")
    internal_token: SecretStr = SecretStr("change-me-internal")
    bot_url: str = "http://bot:9000"
    
    # rag
    rag_data_dir: Path = Path("data/rag-block-03")
    rag_collection: str = "rag_block_03"
    rag_collection_bare: str = "rag_block_03_bare"
    rag_llm_model: str = "gpt-4o-mini"
    rag_top_k: int = 3
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 32
    rag_score_threshold: float = 0.3

@lru_cache
def get_settings() -> Settings:
    return Settings()