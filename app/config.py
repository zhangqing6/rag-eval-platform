from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./data/eval.db"
    judge_api_key: str = ""
    judge_base_url: str = "https://api.openai.com/v1"
    judge_model: str = "gpt-4o-mini"
    http_timeout_seconds: float = 120.0
    max_concurrent_requests: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
