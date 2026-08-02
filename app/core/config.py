from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = ""
    database_url: str = "sqlite+aiosqlite:///life_is_bot.db"
    timezone: str = "Europe/Istanbul"
    default_language: str = "tr"
    scheduler_interval_seconds: int = 60
    scheduler_batch_size: int = 50
    notification_max_retries: int = 3
    notification_retry_intervals: list[int] = [60, 300, 900, 3600]
    notification_retry_batch_size: int = 10
    debug_scheduler: bool = False
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
