from __future__ import annotations

import pytest

from src.core.config import RuntimeSettings, load_runtime_config
from src.main import main


def test_load_runtime_config_resolves_environment(monkeypatch, tmp_path):
    config_path = tmp_path / "runtime.yml"
    config_path.write_text(
        """
        runtime:
          redis:
            url: "${REDIS_URL:-redis://127.0.0.1:6379/0}"
          logging:
            level: "${LOG_LEVEL:-INFO}"
          features:
            scheduler: true
            health_monitor: false
            analytics: true
          analytics:
            enabled: true
            config_path: "config/analytics.yml"
            max_workers: 2
            task_queue_size: 16
            stale_after_seconds: 30
        """
    )

    monkeypatch.setenv("REDIS_URL", "redis://override:6379/9")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    config = load_runtime_config(config_path)
    settings = RuntimeSettings.from_config(config)

    assert settings.redis_url == "redis://override:6379/9"
    assert settings.log_level == "WARNING"
    assert settings.features.as_dict() == {
        "scheduler": True,
        "health_monitor": False,
        "analytics": True,
    }
    assert settings.analytics.as_dict() == {
        "enabled": True,
        "config_path": "config/analytics.yml",
        "max_workers": 2,
        "task_queue_size": 16,
        "stale_after_seconds": 30,
    }


def test_main_dry_run_exit_code(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://dryrun:6379/0")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    exit_code = main(["--dry-run"])

    assert exit_code == 0


def test_load_runtime_config_validation(tmp_path):
    config_path = tmp_path / "runtime.yml"
    config_path.write_text(
        """
        runtime:
          analytics:
            enabled: true
            config_path: "config/analytics.yml"
            max_workers: 0
            task_queue_size: 16
            stale_after_seconds: 30
        """
    )

    with pytest.raises(ValueError, match="max_workers"):
        load_runtime_config(config_path)
