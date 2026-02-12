from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_path: str = "sqlite:///sophia.db"
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8090

    class Config:
        env_file = ".env"

settings = Settings()
