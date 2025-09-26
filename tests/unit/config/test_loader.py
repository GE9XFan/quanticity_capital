"""Tests for the configuration loader."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from quanticity_capital.config.loader import (
    ConfigValidationError,
    MissingEnvironmentVariableError,
    load_settings,
)


def _copy_config_dir(tmp_path: Path) -> Path:
    dest = tmp_path / "config"
    shutil.copytree(PROJECT_ROOT / "config", dest)
    return dest


def _write_env(tmp_path: Path, content: str) -> Path:
    env_path = tmp_path / ".env"
    env_path.write_text(content, encoding="utf-8")
    return env_path


def test_load_settings_success(tmp_path: Path) -> None:
    config_dir = _copy_config_dir(tmp_path)
    env_path = _write_env(tmp_path, "TELEGRAM_WATCHDOG_CHAT_ID=12345\n")

    settings = load_settings(config_dir=config_dir, env_path=env_path, reload=True)

    assert settings.runtime.modules.scheduler is True
    assert settings.runtime.redis.url.startswith("redis://")
    telegram = settings.watchdog.notifications.telegram if settings.watchdog.notifications else None
    assert telegram is not None and telegram.chat_id == "12345"


def test_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_dir = _copy_config_dir(tmp_path)
    env_path = _write_env(tmp_path, "TELEGRAM_WATCHDOG_CHAT_ID=ABC123\n")
    override_url = "redis://override:6379/1"
    monkeypatch.setenv("CONFIG__RUNTIME__REDIS__URL", override_url)

    settings = load_settings(config_dir=config_dir, env_path=env_path, reload=True)

    assert settings.runtime.redis.url == override_url


def test_missing_env_placeholder(tmp_path: Path) -> None:
    config_dir = _copy_config_dir(tmp_path)
    env_path = _write_env(tmp_path, "")

    with pytest.raises(MissingEnvironmentVariableError):
        load_settings(config_dir=config_dir, env_path=env_path, reload=True)


def test_invalid_cron_validation(tmp_path: Path) -> None:
    config_dir = _copy_config_dir(tmp_path)
    env_path = _write_env(tmp_path, "TELEGRAM_WATCHDOG_CHAT_ID=999\n")
    schedule_path = config_dir / "schedule.yml"
    data = schedule_path.read_text(encoding="utf-8")
    schedule_path.write_text(data.replace("*/12 * * * * *", "invalid-cron", 1), encoding="utf-8")

    with pytest.raises(ConfigValidationError):
        load_settings(config_dir=config_dir, env_path=env_path, reload=True)

