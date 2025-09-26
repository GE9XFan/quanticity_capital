"""Test package bootstrap helpers."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure third-party deps installed in the local virtual environment are discoverable
_site_packages = (
    Path(__file__).resolve().parent.parent
    / ".venv"
    / f"lib/python{sys.version_info.major}.{sys.version_info.minor}"
    / "site-packages"
)
if _site_packages.exists():  # pragma: no cover - environment dependent guard
    sys.path.append(str(_site_packages))

__all__ = []
