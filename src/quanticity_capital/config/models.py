"""Typed configuration models for the Quanticity Capital stack."""

from __future__ import annotations

from typing import Dict, List, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from croniter import croniter


class IngestionModuleToggles(BaseModel):
    """Runtime toggles for ingestion submodules."""

    alpha_vantage: bool = True
    ibkr: bool = False

    model_config = ConfigDict(extra="forbid")


class RuntimeModules(BaseModel):
    """Enable/disable modules orchestrated at startup."""

    scheduler: bool = True
    ingestion: IngestionModuleToggles
    analytics: bool = True
    signals: bool = True
    execution: bool = False
    watchdog: bool = True
    social: bool = True
    dashboard_api: bool = True
    observability: bool = True

    model_config = ConfigDict(extra="forbid")


class RedisConfig(BaseModel):
    """Settings for the async Redis client."""

    url: str
    decode_responses: bool = True

    model_config = ConfigDict(extra="forbid")


class PostgresConfig(BaseModel):
    """SQLAlchemy async engine options."""

    dsn: str
    pool_size: int = Field(default=10, ge=1)
    timeout_seconds: int = Field(default=30, ge=1)

    model_config = ConfigDict(extra="forbid")


class RuntimeWatchdogConfig(BaseModel):
    """Toggle between manual and autopilot watchdog modes."""

    mode: Literal["manual", "autopilot"] = "manual"

    model_config = ConfigDict(extra="forbid")


class LoggingConfig(BaseModel):
    """Runtime logging configuration."""

    level: str = "INFO"
    config_file: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class RuntimeConfig(BaseModel):
    """Aggregated runtime configuration."""

    modules: RuntimeModules
    redis: RedisConfig
    postgres: PostgresConfig
    watchdog: RuntimeWatchdogConfig
    logging: LoggingConfig

    model_config = ConfigDict(extra="forbid")


class ScheduleBucketConfig(BaseModel):
    """Token bucket definition used for scheduler throttling."""

    capacity: int = Field(ge=1)
    refill_per_second: float = Field(gt=0)

    model_config = ConfigDict(extra="forbid")


class ScheduleJobConfig(BaseModel):
    """Individual scheduled job definition."""

    cadence: str
    bucket: Optional[str] = None
    jitter_seconds: Optional[int] = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("cadence")
    @classmethod
    def validate_cron_expression(cls, value: str) -> str:
        if not croniter.is_valid(value):
            msg = f"Invalid cron cadence '{value}'"
            raise ValueError(msg)
        return value


class ScheduleConfig(BaseModel):
    """Scheduler configuration payload."""

    buckets: Dict[str, ScheduleBucketConfig]
    jobs: Dict[str, ScheduleJobConfig]

    model_config = ConfigDict(extra="forbid")


class SymbolsIngestionAlphaVantage(BaseModel):
    realtime_options: List[str]
    tech_indicators: List[str]
    news_sentiment: List[str]

    model_config = ConfigDict(extra="forbid")


class SymbolsIngestionIBKR(BaseModel):
    l2_rotation_groups: List[List[str]]

    model_config = ConfigDict(extra="forbid")


class SymbolsIngestionConfig(BaseModel):
    alpha_vantage: SymbolsIngestionAlphaVantage
    ibkr: SymbolsIngestionIBKR

    model_config = ConfigDict(extra="forbid")


class SymbolsSignalsConfig(BaseModel):
    strategies: Dict[str, List[str]]

    model_config = ConfigDict(extra="forbid")


class SymbolsConfig(BaseModel):
    """Symbol universe definition and capability flags."""

    universes: Dict[str, List[str]]
    ingestion: SymbolsIngestionConfig
    signals: SymbolsSignalsConfig

    model_config = ConfigDict(extra="forbid")


class AnalyticsMetricConfig(BaseModel):
    """Flexible metric configuration with required enable toggle."""

    enabled: bool = True

    model_config = ConfigDict(extra="allow")


class AnalyticsConfig(BaseModel):
    metrics: Dict[str, AnalyticsMetricConfig]

    model_config = ConfigDict(extra="forbid")


class WatchdogNotificationsTelegram(BaseModel):
    enabled: bool = False
    chat_id: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class WatchdogNotificationsConfig(BaseModel):
    telegram: Optional[WatchdogNotificationsTelegram] = None

    model_config = ConfigDict(extra="forbid")


class WatchdogConfig(BaseModel):
    """OpenAI watchdog configuration."""

    mode: Literal["manual", "autopilot"] = "manual"
    confidence_thresholds: Mapping[str, float]
    rate_limits: Mapping[str, int]
    model: str
    prompt_templates: Mapping[str, str]
    notifications: Optional[WatchdogNotificationsConfig] = None

    model_config = ConfigDict(extra="forbid")


class AlertingChannelConfig(BaseModel):
    enabled: bool = False
    bot_token_env: Optional[str] = None
    chat_id_env: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class AlertingConfig(BaseModel):
    telegram: Optional[AlertingChannelConfig] = None
    email: Optional[AlertingChannelConfig] = None

    model_config = ConfigDict(extra="forbid")


class ObservabilityLoggingConfig(BaseModel):
    log_dir: str
    max_bytes: int = Field(gt=0)
    backups: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class ObservabilityConfig(BaseModel):
    """Operational observability thresholds and routing."""

    heartbeats: Mapping[str, int]
    data_freshness: Mapping[str, int]
    alerting: AlertingConfig
    logging: ObservabilityLoggingConfig

    model_config = ConfigDict(extra="forbid")


class AppConfig(BaseModel):
    """Top-level configuration container."""

    runtime: RuntimeConfig
    schedule: ScheduleConfig
    symbols: SymbolsConfig
    analytics: AnalyticsConfig
    watchdog: WatchdogConfig
    observability: ObservabilityConfig

    model_config = ConfigDict(extra="forbid")


__all__ = [
    "AlertingChannelConfig",
    "AlertingConfig",
    "AnalyticsConfig",
    "AnalyticsMetricConfig",
    "AppConfig",
    "LoggingConfig",
    "ObservabilityConfig",
    "ObservabilityLoggingConfig",
    "PostgresConfig",
    "RedisConfig",
    "RuntimeConfig",
    "RuntimeModules",
    "RuntimeWatchdogConfig",
    "ScheduleBucketConfig",
    "ScheduleConfig",
    "ScheduleJobConfig",
    "SymbolsConfig",
    "SymbolsIngestionAlphaVantage",
    "SymbolsIngestionConfig",
    "SymbolsIngestionIBKR",
    "SymbolsSignalsConfig",
    "WatchdogConfig",
    "WatchdogNotificationsConfig",
    "WatchdogNotificationsTelegram",
]

