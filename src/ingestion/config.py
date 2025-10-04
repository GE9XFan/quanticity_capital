"""Configuration models for the ingestion worker."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionSettings(BaseSettings):
    """Runtime configuration for the Unusual Whales ingestion worker."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    unusual_whales_api_token: SecretStr
    redis_url: str = Field(default="redis://localhost:6379/0")
    database_url: str = Field(default="postgresql://quanticity:quanticity@localhost:5432/trading")
    websocket_url: str = Field(
        default="wss://api.unusualwhales.com/socket",
        description="WebSocket endpoint including protocol and host.",
    )
    rest_base_url: str = Field(default="https://api.unusualwhales.com")
    target_tickers: tuple[str, ...] = Field(default=("SPY", "QQQ", "IWM"))
    option_trade_buffer_size: int = Field(default=1000)
    option_trade_flush_seconds: float = Field(default=2.0)
    option_trade_stream_prefix: str = Field(default="uw:option_trades")
    gex_snapshot_prefix: str = Field(default="latest:uw:gex")
    gex_strike_snapshot_prefix: str = Field(default="latest:uw:gex_strike")
    gex_strike_expiry_snapshot_prefix: str = Field(default="latest:uw:gex_strike_expiry")
    news_pubsub_channel: str = Field(default="uw:news")
    price_bar_stream_prefix: str = Field(default="uw:price_bars_1m")
    flow_alert_stream_key: str = Field(default="uw:flow_alerts")
    flow_alert_stream_maxlen: int = Field(default=10_000)
    price_stream_prefix: str = Field(default="uw:price_ticks")
    price_snapshot_prefix: str = Field(default="latest:uw:price")
    flow_alert_snapshot_prefix: str = Field(default="latest:uw:flow_alert")
    environment: Literal["development", "staging", "production"] = Field(default="development")
    reconnect_min_seconds: float = Field(default=5.0)
    reconnect_max_seconds: float = Field(default=60.0)
    reconnect_max_attempts: int = Field(default=5)
    websocket_ping_interval: float = Field(default=20.0)
    websocket_ping_timeout: float = Field(default=20.0)
    inactivity_timeout_seconds: float = Field(default=15.0)
    rate_limit_tokens_per_minute: int = Field(default=120)
    rate_limit_reserve_tokens: int = Field(default=24)
    rest_job_poll_interval: float = Field(default=5.0)
    rest_job_cadences: dict[str, int] = Field(
        default_factory=lambda: {
            "stock_flow_alerts": 120,
            "stock_flow_per_expiry": 300,
            "stock_greek_exposure": 300,
            "stock_greek_exposure_expiry": 600,
            "stock_greek_exposure_strike": 600,
            "stock_greek_flow": 300,
            "stock_interpolated_iv": 600,
            "stock_iv_rank": 900,
            "stock_max_pain": 900,
            "stock_net_prem_ticks": 300,
            "stock_nope": 300,
            "stock_ohlc_1m": 120,
            "stock_oi_change": 600,
            "stock_option_chains": 900,
            "stock_option_stock_price_levels": 600,
            "stock_options_volume": 600,
            "stock_spot_exposures": 300,
            "stock_spot_exposures_strike": 600,
            "stock_stock_state": 300,
            "stock_stock_volume_price_levels": 300,
            "stock_volatility_realized": 600,
            "stock_volatility_stats": 600,
            "stock_volatility_term_structure": 900,
            "stock_darkpool": 300,
            "etf_exposure": 900,
            "etf_in_outflow": 900,
            "market_etf_tide": 600,
            "market_economic_calendar": 3600,
            "market_market_tide": 300,
            "market_oi_change": 900,
            "market_top_net_impact": 600,
            "market_total_options_volume": 600,
            "net_flow_expiry": 900,
        }
    )
    rest_timeout_seconds: float = Field(default=15.0)
    enable_disk_spooling: bool = Field(default=False)


__all__ = ["IngestionSettings"]
