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
    # 简易评测台：本地 Ollama 直连（与 scripts/mock_agent 一致）
    ollama_base: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    # 限制 Ollama 最多生成多少 token（省显存/时间；None 表示不传给 Ollama，由模型默认）
    ollama_num_predict: int | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
