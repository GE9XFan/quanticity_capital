"""Quanticity Capital core package.

Provides shared helpers and a CLI bootstrap hook for the data platform.
"""

from __future__ import annotations

import logging

__all__ = ["bootstrap_logging", "__version__"]

__version__ = "0.1.0"


def bootstrap_logging(level: int | str | None = "INFO") -> None:
    """Initialise a basic logging configuration for the CLI entrypoints."""

    if isinstance(level, str):
        level = level.upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

