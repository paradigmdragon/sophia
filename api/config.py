from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    db_path: str = "sqlite:///sophia.db"
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8090
    enable_watchers: bool = Field(default=True, validation_alias="SOPHIA_ENABLE_WATCHERS")
    watcher_interval_seconds: int = Field(default=3600, validation_alias="SOPHIA_WATCHER_INTERVAL_SECONDS")
    watcher_startup_delay_seconds: int = Field(default=30, validation_alias="SOPHIA_WATCHER_STARTUP_DELAY_SECONDS")
    watcher_threshold_days: int = Field(default=7, validation_alias="SOPHIA_WATCHER_THRESHOLD_DAYS")
    watcher_cooldown_days: int = Field(default=3, validation_alias="SOPHIA_WATCHER_COOLDOWN_DAYS")
    watcher_daily_limit: int = Field(default=1, validation_alias="SOPHIA_WATCHER_DAILY_LIMIT")

    class Config:
        env_file = ".env"

settings = Settings()
