"""Load configuration from YAML files and environment variables."""

from __future__ import annotations

from .models import (
    AnalyticsConfig,
    AppConfig,
    ObservabilityConfig,
    RuntimeConfig,
    ScheduleConfig,
    SymbolsConfig,
    WatchdogConfig,
)

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]

try:  # pragma: no cover - fallback path resolution
    import yaml  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover
    fallback = (
        REPO_ROOT
        / ".venv"
        / f"lib/python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    if fallback.exists():
        sys.path.insert(0, str(fallback))
        import yaml  # type: ignore
    else:
        raise exc


class ConfigError(RuntimeError):
    """Base class for configuration related issues."""


class MissingEnvironmentVariableError(ConfigError):
    """Raised when a placeholder references an undefined environment variable."""


class ConfigValidationError(ConfigError):
    """Wraps validation errors thrown by Pydantic."""


ENV_PLACEHOLDER_PATTERN = re.compile(r"\$\{([^}:]+)(?::-(.*?))?\}")
ENV_OVERRIDE_PREFIX = "CONFIG__"

DEFAULT_CONFIG_DIR = REPO_ROOT / "config"
DEFAULT_ENV_FILE = REPO_ROOT / ".env"


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Configuration file missing: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"Configuration file {path} must contain a mapping")
    return data


def _load_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    env: Dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if not sep:
                continue
            env[key.strip()] = _strip_quotes(value.strip())
    return env


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _resolve_placeholders(obj: Any, env: Mapping[str, str]) -> Any:
    if isinstance(obj, dict):
        return {key: _resolve_placeholders(value, env) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_resolve_placeholders(item, env) for item in obj]
    if isinstance(obj, str):
        return _replace_placeholders(obj, env)
    return obj


def _replace_placeholders(value: str, env: Mapping[str, str]) -> str:
    def replacer(match: re.Match[str]) -> str:
        variable, default = match.group(1), match.group(2)
        if variable in env and env[variable] != "":
            return env[variable]
        if variable in os.environ and os.environ[variable] != "":
            return os.environ[variable]
        if default is not None:
            return default
        raise MissingEnvironmentVariableError(
            f"Environment variable '{variable}' is required for configuration"
        )

    return ENV_PLACEHOLDER_PATTERN.sub(replacer, value)


def _apply_env_overrides(data: MutableMapping[str, Any], env: Mapping[str, str]) -> None:
    for key, value in env.items():
        if not key.startswith(ENV_OVERRIDE_PREFIX):
            continue
        path = key[len(ENV_OVERRIDE_PREFIX) :].split("__")
        if not path:
            continue
        _assign_path(data, [segment.lower() for segment in path], _coerce_value(value))

    for key, value in os.environ.items():
        if not key.startswith(ENV_OVERRIDE_PREFIX):
            continue
        path = key[len(ENV_OVERRIDE_PREFIX) :].split("__")
        if not path:
            continue
        _assign_path(data, [segment.lower() for segment in path], _coerce_value(value))


def _assign_path(data: MutableMapping[str, Any], path: Iterable[str], value: Any) -> None:
    cursor: MutableMapping[str, Any] = data
    segments = list(path)
    for segment in segments[:-1]:
        if segment not in cursor or not isinstance(cursor[segment], MutableMapping):
            cursor[segment] = {}
        cursor = cursor[segment]  # type: ignore[assignment]
    cursor[segments[-1]] = value


def _coerce_value(value: str) -> Any:
    raw = value.strip()
    if raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return value


def _build_models(payloads: Dict[str, Dict[str, Any]]) -> AppConfig:
    try:
        runtime = RuntimeConfig.model_validate(payloads["runtime"])
        schedule = ScheduleConfig.model_validate(payloads["schedule"])
        symbols = SymbolsConfig.model_validate(payloads["symbols"])
        analytics = AnalyticsConfig.model_validate(payloads["analytics"])
        watchdog = WatchdogConfig.model_validate(payloads["watchdog"])
        observability = ObservabilityConfig.model_validate(payloads["observability"])
        return AppConfig(
            runtime=runtime,
            schedule=schedule,
            symbols=symbols,
            analytics=analytics,
            watchdog=watchdog,
            observability=observability,
        )
    except Exception as exc:  # pragma: no cover - wrapped for context
        raise ConfigValidationError(str(exc)) from exc


_SETTINGS_CACHE: Dict[Tuple[Path, Path], AppConfig] = {}


def load_settings(
    *,
    config_dir: Optional[Path] = None,
    env_path: Optional[Path] = None,
    reload: bool = False,
) -> AppConfig:
    """Load configuration from disk, applying environment overrides."""

    directory = (config_dir or DEFAULT_CONFIG_DIR).resolve()
    environment_file = (env_path or DEFAULT_ENV_FILE).resolve()
    cache_key = (directory, environment_file)

    if not reload and cache_key in _SETTINGS_CACHE:
        return _SETTINGS_CACHE[cache_key]

    env_values = _load_env_file(environment_file)
    merged_env: Dict[str, str] = {**env_values, **dict(os.environ)}

    payloads = {
        "runtime": _load_yaml(directory / "runtime.yml"),
        "schedule": _load_yaml(directory / "schedule.yml"),
        "symbols": _load_yaml(directory / "symbols.yml"),
        "analytics": _load_yaml(directory / "analytics.yml"),
        "watchdog": _load_yaml(directory / "watchdog.yml"),
        "observability": _load_yaml(directory / "observability.yml"),
    }

    substituted = {
        name: _resolve_placeholders(content, merged_env) for name, content in payloads.items()
    }

    _apply_env_overrides(substituted, env_values)

    settings = _build_models(substituted)
    _SETTINGS_CACHE[cache_key] = settings
    return settings


__all__ = [
    "AppConfig",
    "ConfigError",
    "ConfigValidationError",
    "MissingEnvironmentVariableError",
    "load_settings",
]
