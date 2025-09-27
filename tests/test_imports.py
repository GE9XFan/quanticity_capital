"""Smoke checks for the repository skeleton."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest


def test_package_imports() -> None:
    module = import_module("quanticity_capital")
    assert hasattr(module, "bootstrap_logging")


def test_cli_main_returns_zero() -> None:
    from quanticity_capital.main import main

    exit_code = main(["--log-level", "DEBUG"])
    assert exit_code == 0


def test_cli_alpha_vantage_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from quanticity_capital.main import main

    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        """
services:
  alphavantage:
    base_url: https://www.alphavantage.co
    api_key_env: TEST_ALPHA_KEY
ingestion:
  alpha_vantage:
    enabled_endpoints:
      - EARNINGS_CALL_TRANSCRIPT
    endpoints:
      EARNINGS_CALL_TRANSCRIPT:
        contexts:
          - symbol: NVDA
            quarter: 2024Q4
"""
    )

    monkeypatch.setenv("TEST_ALPHA_KEY", "dummy-key")

    exit_code = main(
        [
            "--log-level",
            "INFO",
            "ingest",
            "alpha-vantage",
            "--settings",
            str(settings_file),
            "--dry-run",
        ]
    )

    assert exit_code == 0


def test_cli_alpha_vantage_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from quanticity_capital.main import main

    env_file = tmp_path / ".env"
    env_file.write_text("TEST_ALPHA_KEY=env-file-key\n")

    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        """
services:
  alphavantage:
    base_url: https://www.alphavantage.co
    api_key_env: TEST_ALPHA_KEY
ingestion:
  alpha_vantage:
    enabled_endpoints:
      - EARNINGS_CALL_TRANSCRIPT
    endpoints:
      EARNINGS_CALL_TRANSCRIPT:
        contexts:
          - symbol: MSFT
            quarter: 2024Q3
"""
    )

    monkeypatch.delenv("TEST_ALPHA_KEY", raising=False)
    monkeypatch.setenv("QUANTICITY_ENV_FILE", str(env_file))

    exit_code = main(
        [
            "--log-level",
            "INFO",
            "ingest",
            "alpha-vantage",
            "--settings",
            str(settings_file),
            "--dry-run",
        ]
    )

    assert exit_code == 0
