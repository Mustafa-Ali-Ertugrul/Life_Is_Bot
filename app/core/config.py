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
    notification_max_retries: int = 4
    notification_retry_intervals: list[int] = [60, 300, 900, 3600]
    notification_retry_batch_size: int = 10
    debug_scheduler: bool = False
    log_level: str = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_cors_origins: list[str] = ["*"]
    api_auth_max_age: int = 86400
    api_key: str = ""
    webhook_mode: bool = False
    telegram_webhook_url: str = ""
    telegram_webhook_secret: str = ""
    backup_enabled: bool = True
    backup_dir: str = "backups"
    backup_retention_days: int = 30
    reports_dir: str = "reports"
    auto_monthly_report: bool = True
    purge_enabled: bool = False
    data_retention_months: int = 1
    rate_limit_enabled: bool = True
    rate_limit_crud_per_minute: int = 60
    rate_limit_reports_per_minute: int = 30
    rate_limit_storage_uri: str = "memory://"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
