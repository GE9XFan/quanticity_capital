"""Analytics configuration loader."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional
import os
import re

import yaml

_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(:-([^}]*))?\}")


@dataclass
class AnalyticsJobConfig:
    """Configuration for an analytics refresh job."""

    name: str
    job_type: str
    enabled: bool
    cadence_seconds: int
    symbols: tuple[str, ...]
    metrics: tuple[str, ...]

    def validate(self) -> None:
        if not self.name:
            raise ValueError("analytics job name cannot be empty")
        if not self.job_type:
            raise ValueError(f"analytics job '{self.name}' missing type")
        if self.cadence_seconds < 1:
            raise ValueError(
                f"analytics job '{self.name}' has invalid cadence_seconds: {self.cadence_seconds}"
            )
        if not self.symbols:
            raise ValueError(f"analytics job '{self.name}' must specify at least one symbol")
        if not self.metrics:
            raise ValueError(f"analytics job '{self.name}' must specify at least one metric")

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type": self.job_type,
            "enabled": self.enabled,
            "cadence_seconds": self.cadence_seconds,
            "symbols": list(self.symbols),
            "metrics": list(self.metrics),
        }


@dataclass
class AnalyticsJobs:
    """Container for configured analytics jobs."""

    jobs: tuple[AnalyticsJobConfig, ...]

    def enabled(self) -> tuple[AnalyticsJobConfig, ...]:
        return tuple(job for job in self.jobs if job.enabled)

    def __iter__(self) -> Iterable[AnalyticsJobConfig]:
        return iter(self.jobs)


def load_analytics_config(
    path: Path | str = Path("config/analytics.yml"),
    *,
    env: Optional[Mapping[str, str]] = None,
) -> AnalyticsJobs:
    """Load analytics config file and return job definitions."""

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Analytics configuration file not found: {config_path}")

    raw_text = config_path.read_text()
    rendered = _substitute_environment(raw_text, env or os.environ)
    payload = yaml.safe_load(rendered) or {}

    defaults = payload.get("defaults", {})
    default_enabled = bool(defaults.get("enabled", True))
    default_cadence = int(defaults.get("cadence_seconds", 60))

    jobs_section = payload.get("jobs", [])
    jobs: list[AnalyticsJobConfig] = []
    for entry in jobs_section:
        if not isinstance(entry, dict):
            raise ValueError(f"Invalid analytics job entry: {entry!r}")

        name = str(entry.get("name", "")).strip()
        job_type = str(entry.get("type", "")).strip()
        enabled = bool(entry.get("enabled", default_enabled))
        cadence_raw = entry.get("cadence_seconds", default_cadence)
        cadence_seconds = _coerce_positive_int(
            cadence_raw, f"analytics job '{name or job_type}' cadence_seconds"
        )
        symbols = entry.get("symbols", [])
        metrics = entry.get("metrics", [])

        job = AnalyticsJobConfig(
            name=name,
            job_type=job_type,
            enabled=enabled,
            cadence_seconds=cadence_seconds,
            symbols=_tuple_of_strings(symbols, "symbols", name),
            metrics=_tuple_of_strings(metrics, "metrics", name),
        )
        job.validate()
        jobs.append(job)

    return AnalyticsJobs(jobs=tuple(jobs))


def _substitute_environment(template: str, env: Mapping[str, str]) -> str:
    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default = match.group(3) or ""
        return env.get(var_name, default)

    return _ENV_PATTERN.sub(replacer, template)


def _tuple_of_strings(value: object, field: str, job_name: str) -> tuple[str, ...]:
    if value is None:
        return tuple()
    if isinstance(value, str):
        return (value,)
    try:
        items = tuple(str(item).strip() for item in value)
    except TypeError as exc:  # pragma: no cover - defensive guard
        raise ValueError(
            f"analytics job '{job_name}' field '{field}' must be iterable of strings"
        ) from exc
    return tuple(item for item in items if item)


def _coerce_positive_int(value: object, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid integer for {field_name}: {value}") from exc
    if parsed < 1:
        raise ValueError(f"{field_name} must be >= 1 (got {parsed})")
    return parsed


__all__ = ["AnalyticsJobConfig", "AnalyticsJobs", "load_analytics_config"]
