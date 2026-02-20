from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    db_path: str = "sqlite:///sophia.db"
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8090
    ai_provider_default: str = Field(default="ollama", validation_alias="AI_PROVIDER_DEFAULT")
    ai_mode: str = Field(default="fallback", validation_alias="AI_MODE")
    ai_divergence_threshold: float = Field(default=0.35, validation_alias="AI_DIVERGENCE_THRESHOLD")
    ai_allow_external: bool = Field(default=False, validation_alias="AI_ALLOW_EXTERNAL")
    ai_foundation_bridge_url: str = Field(
        default="http://127.0.0.1:8765",
        validation_alias="AI_FOUNDATION_BRIDGE_URL",
    )
    shortcuts_secret: str = Field(default="", validation_alias="SHORTCUT_SECRET")
    shortcuts_integration_status: str = Field(
        default="UNVERIFIED",
        validation_alias="SOPHIA_SHORTCUTS_STATUS",
    )
    enable_watchers: bool = Field(default=True, validation_alias="SOPHIA_ENABLE_WATCHERS")
    watcher_interval_seconds: int = Field(default=3600, validation_alias="SOPHIA_WATCHER_INTERVAL_SECONDS")
    watcher_startup_delay_seconds: int = Field(default=30, validation_alias="SOPHIA_WATCHER_STARTUP_DELAY_SECONDS")
    watcher_threshold_days: int = Field(default=7, validation_alias="SOPHIA_WATCHER_THRESHOLD_DAYS")
    watcher_cooldown_days: int = Field(default=3, validation_alias="SOPHIA_WATCHER_COOLDOWN_DAYS")
    watcher_daily_limit: int = Field(default=1, validation_alias="SOPHIA_WATCHER_DAILY_LIMIT")
    forest_auto_sync: bool = Field(default=False, validation_alias="SOPHIA_FOREST_AUTO_SYNC")
    forest_focus_mode: bool = Field(default=True, validation_alias="SOPHIA_FOREST_FOCUS_MODE")
    forest_focus_lock_level: str = Field(default="soft", validation_alias="SOPHIA_FOREST_FOCUS_LOCK_LEVEL")
    forest_wip_limit: int = Field(default=1, validation_alias="SOPHIA_FOREST_WIP_LIMIT")
    forest_freeze_daily_limit: int = Field(default=10, validation_alias="SOPHIA_FOREST_FREEZE_DAILY_LIMIT")

    class Config:
        env_file = ".env"

settings = Settings()
