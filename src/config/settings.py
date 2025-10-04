"""Settings configuration for Unusual Whales REST ingestion."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment & Redis (kept for future integrations)
    environment: str = Field(default="development", description="Environment label for logging")
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL (unused in Phase 0)")

    # Unusual Whales API
    unusual_whales_api_token: str = Field(..., description="API token for Unusual Whales access")

    # Target symbols
    target_symbols: str = Field(default="SPY,QQQ,IWM", description="Comma-separated list of tickers to fetch")
    store_to_redis: bool = Field(default=True, description="Whether to upsert snapshots into Redis")
    fetch_interval_seconds: float = Field(
        default=0.0,
        description="Loop interval in seconds (0 disables looping)",
    )

    # Request configuration
    request_timeout_seconds: float = Field(default=30.0, description="HTTP request timeout in seconds")

    # Rate limiting
    rate_limit_requests_per_minute: int = Field(default=100, description="Max requests per minute (hard limit 120)")
    rate_limit_leeway_seconds: float = Field(default=0.5, description="Extra delay between requests for safety")

    @property
    def symbols(self) -> list[str]:
        """Parse target symbols into a list."""
        return [s.strip() for s in self.target_symbols.split(",") if s.strip()]

    @property
    def rate_limit_delay(self) -> float:
        """Calculate minimum delay between requests based on rate limit."""
        # Convert requests per minute to delay in seconds
        min_delay = 60.0 / self.rate_limit_requests_per_minute
        return min_delay + self.rate_limit_leeway_seconds


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
