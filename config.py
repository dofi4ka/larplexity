from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    telegram_bot_token: SecretStr
    allowed_user_ids: list[int] = Field(default_factory=list)

    # LLM (OpenAI-compatible, e.g. DeepSeek)
    llm_api_key: SecretStr
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 3

    # Tools
    tavily_api_key: SecretStr | None = None
    http_timeout_seconds: float = 30.0
    http_max_retries: int = 3
    max_webpage_chars: int = 20_000
    max_search_results: int = 8

    # Storage
    sqlite_path: Path = Path("data/bot.db")
    uploads_dir: Path = Path("uploads")
    max_upload_bytes: int = 5 * 1024 * 1024
    allowed_upload_extensions: list[str] = Field(
        default_factory=lambda: [".txt", ".md", ".csv", ".json", ".log", ".py", ".pdf"]
    )

    # Memory / RAG
    chunk_size: int = 800
    chunk_overlap: int = 120
    retrieval_top_k: int = 8
    include_prior_chats_by_default: bool = True
    prior_chats_limit: int = 5
    summarize_every_n_messages: int = 20

    # Rate limiting
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 60

    # Research
    research_max_queries: int = 5
    research_max_sources: int = 10

    # Infra
    log_level: str = "INFO"
    health_host: str = "0.0.0.0"
    health_port: int = 8080
    chats_page_size: int = 5

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def parse_user_ids(cls, value: object) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(v) for v in value]
        if isinstance(value, int):
            return [value]
        text = str(value).strip()
        if not text:
            return []
        return [int(part.strip()) for part in text.split(",") if part.strip()]

    @field_validator("allowed_upload_extensions", mode="before")
    @classmethod
    def parse_extensions(cls, value: object) -> list[str]:
        if value is None or value == "":
            return [".txt", ".md", ".csv", ".json", ".log", ".py", ".pdf"]
        if isinstance(value, list):
            items = value
        else:
            items = [part.strip() for part in str(value).split(",") if part.strip()]
        normalized: list[str] = []
        for item in items:
            ext = item if item.startswith(".") else f".{item}"
            normalized.append(ext.lower())
        return normalized


@lru_cache
def get_settings() -> Settings:
    settings = Settings()  # type: ignore[call-arg]
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    return settings
