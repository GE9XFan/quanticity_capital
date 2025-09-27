"""Structured logging helpers for the Quanticity Capital stack."""
from __future__ import annotations

import logging

import structlog


def configure_logging(level: str) -> None:
    """Configure structlog with sensible JSON defaults."""

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format="%(message)s",
    )

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


__all__ = ["configure_logging"]
