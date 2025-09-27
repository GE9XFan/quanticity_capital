"""Configuration helpers for the Quanticity Capital platform."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

_DEFAULT_SETTINGS_PATHS = (
    Path("config/settings.yaml"),
    Path("config/settings.example.yaml"),
)


def load_settings(path: str | Path | None = None) -> dict[str, Any]:
    """Load settings from YAML, preferring `config/settings.yaml` when available."""

    candidates: tuple[Path, ...]
    if path is not None:
        candidate_path = Path(path)
        if not candidate_path.is_file():
            raise FileNotFoundError(f"Settings file not found: {candidate_path}")
        candidates = (candidate_path,)
    else:
        candidates = tuple(p for p in _DEFAULT_SETTINGS_PATHS if p.is_file())

    if not candidates:
        raise FileNotFoundError(
            "No settings file found. Provide config/settings.yaml or config/settings.example.yaml."
        )

    for candidate in candidates:
        data = yaml.safe_load(candidate.read_text())
        if data is None:
            return {}
        if isinstance(data, Mapping):
            return dict(data)
        raise TypeError(f"Settings file '{candidate}' must contain a YAML mapping, got {type(data)!r}")

    # This should not be reachable due to the loop return.
    raise RuntimeError("Unable to load settings")


__all__ = ["load_settings"]
