"""Tests for configuration helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from quanticity_capital.config import load_settings


def test_load_settings_from_explicit_path(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text("""
services:
  alphavantage:
    api_key_env: CUSTOM_KEY
""")

    data = load_settings(settings_file)

    assert data["services"]["alphavantage"]["api_key_env"] == "CUSTOM_KEY"


def test_load_settings_requires_mapping(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text("- not-a-mapping")

    with pytest.raises(TypeError):
        load_settings(settings_file)


def test_load_settings_prefers_repo_defaults() -> None:
    data = load_settings()
    assert isinstance(data, dict)
    assert "services" in data
