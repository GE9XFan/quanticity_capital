"""Application configuration models."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    app_name: str = Field(default="Quanticity Trading Platform")
    env: str = Field(default="development")
    redis_url: str = Field(default="redis://localhost:6379/0")
    database_url: str = Field(default="postgresql://quanticity:quanticity@localhost:5432/trading")
    unusual_whales_api_token: str | None = None
    ib_client_id: int | None = None
    ib_host: str = Field(default="127.0.0.1")
    ib_port: int = Field(default=7497)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
