"""Runtime configuration loader for the Quanticity Capital system."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional
import os
import re

import yaml

_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(:-([^}]*))?\}")


@dataclass
class RedisConfig:
    url: str


@dataclass
class LoggingConfig:
    level: str


@dataclass
class FeatureFlags:
    scheduler: bool
    health_monitor: bool
    analytics: bool

    def as_dict(self) -> dict[str, bool]:
        return {
            "scheduler": self.scheduler,
            "health_monitor": self.health_monitor,
            "analytics": self.analytics,
        }


@dataclass
class AnalyticsConfig:
    enabled: bool
    config_path: str
    max_workers: int
    task_queue_size: int
    stale_after_seconds: int

    def validate(self) -> None:
        if self.max_workers < 1:
            raise ValueError("analytics.max_workers must be at least 1")
        if self.task_queue_size < 1:
            raise ValueError("analytics.task_queue_size must be at least 1")
        if self.stale_after_seconds < 1:
            raise ValueError("analytics.stale_after_seconds must be at least 1")

    def as_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "config_path": self.config_path,
            "max_workers": self.max_workers,
            "task_queue_size": self.task_queue_size,
            "stale_after_seconds": self.stale_after_seconds,
        }


@dataclass
class RuntimeConfig:
    redis: RedisConfig
    logging: LoggingConfig
    features: FeatureFlags
    analytics: AnalyticsConfig


@dataclass
class RuntimeSettings:
    redis_url: str
    log_level: str
    features: FeatureFlags
    analytics: AnalyticsConfig

    @classmethod
    def from_config(cls, config: RuntimeConfig) -> "RuntimeSettings":
        return cls(
            redis_url=config.redis.url,
            log_level=config.logging.level,
            features=config.features,
            analytics=config.analytics,
        )


def load_runtime_config(
    path: Path | str = Path("config/runtime.yml"), *, env: Optional[Mapping[str, str]] = None
) -> RuntimeConfig:
    """Load the runtime configuration file and resolve environment placeholders."""

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Runtime configuration file not found: {config_path}")

    raw_text = config_path.read_text()
    rendered_text = _substitute_environment(raw_text, env or os.environ)
    payload = yaml.safe_load(rendered_text) or {}
    runtime_section = payload.get("runtime", {})

    redis_section = runtime_section.get("redis", {})
    logging_section = runtime_section.get("logging", {})
    features_section = runtime_section.get("features", {})
    analytics_section = runtime_section.get("analytics", {})

    redis_config = RedisConfig(url=redis_section.get("url", "redis://127.0.0.1:6379/0"))
    logging_config = LoggingConfig(level=logging_section.get("level", "INFO"))
    feature_flags = FeatureFlags(
        scheduler=bool(features_section.get("scheduler", True)),
        health_monitor=bool(features_section.get("health_monitor", True)),
        analytics=bool(features_section.get("analytics", False)),
    )
    analytics_config = AnalyticsConfig(
        enabled=bool(analytics_section.get("enabled", False)),
        config_path=str(analytics_section.get("config_path", "config/analytics.yml")),
        max_workers=_coerce_int(analytics_section.get("max_workers", 4), "analytics.max_workers"),
        task_queue_size=_coerce_int(
            analytics_section.get("task_queue_size", 64), "analytics.task_queue_size"
        ),
        stale_after_seconds=_coerce_int(
            analytics_section.get("stale_after_seconds", 45),
            "analytics.stale_after_seconds",
        ),
    )
    analytics_config.validate()

    return RuntimeConfig(
        redis=redis_config,
        logging=logging_config,
        features=feature_flags,
        analytics=analytics_config,
    )


def _substitute_environment(template: str, env: Mapping[str, str]) -> str:
    """Replace shell-style placeholders with environment values."""

    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default = match.group(3) or ""
        return env.get(var_name, default)

    return _ENV_PATTERN.sub(replacer, template)


def _coerce_int(value: object, name: str) -> int:
    try:
        coerced = int(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Invalid integer for {name}: {value}") from exc
    return coerced


__all__ = [
    "AnalyticsConfig",
    "FeatureFlags",
    "LoggingConfig",
    "RedisConfig",
    "RuntimeConfig",
    "RuntimeSettings",
    "load_runtime_config",
]
