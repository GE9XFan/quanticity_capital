"""Shared accessor for application settings."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import AppConfig, load_settings


def get_settings(
    *,
    reload: bool = False,
    config_dir: Optional[Path] = None,
    env_path: Optional[Path] = None,
) -> AppConfig:
    """Return the cached application settings."""

    return load_settings(config_dir=config_dir, env_path=env_path, reload=reload)


__all__ = ["get_settings", "AppConfig"]
