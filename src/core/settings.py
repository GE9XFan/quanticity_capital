"""Configuration loading helpers shared across the project."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

import structlog
import yaml
from dotenv import load_dotenv

LOGGER = structlog.get_logger()
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    contents = yaml.safe_load(path.read_text())
    if not contents:
        return {}
    if not isinstance(contents, dict):
        raise ValueError(f"Configuration file {path} must load into a mapping.")
    return contents


def load_runtime_config() -> Dict[str, Any]:
    """Load JSON runtime configuration if present."""
    return _read_json(CONFIG_DIR / "runtime.json")


def load_alpha_config() -> Dict[str, Any]:
    """Load Alpha Vantage configuration if present."""
    return _read_yaml(CONFIG_DIR / "alpha_vantage.yml")


def load_configuration() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Load environment variables and configuration files in a predictable order."""
    load_dotenv()
    runtime_config = load_runtime_config()
    alpha_config = load_alpha_config()
    LOGGER.info(
        "configuration.loaded",
        load_order=[".env", "config/runtime.json", "config/alpha_vantage.yml"],
        runtime_keys=list(runtime_config.keys()),
        alpha_endpoints=list(alpha_config.get("endpoints", {}).keys()),
    )
    return runtime_config, alpha_config


__all__ = [
    "CONFIG_DIR",
    "PROJECT_ROOT",
    "load_runtime_config",
    "load_alpha_config",
    "load_configuration",
]
