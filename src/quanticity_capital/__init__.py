"""Quanticity Capital core package.

Provides shared helpers and a CLI bootstrap hook for the data platform.
"""

from __future__ import annotations

import logging

import structlog

from .config import load_settings
from .orchestrator import AlphaVantageOrchestrator
from .scheduler import AlphaVantageScheduler
from .runner import IngestionJob, RateLimiter, RetryPolicy, Runner, RunnerResult

__all__ = [
    "bootstrap_logging",
    "__version__",
    "IngestionJob",
    "RateLimiter",
    "RetryPolicy",
    "Runner",
    "RunnerResult",
    "AlphaVantageOrchestrator",
    "AlphaVantageScheduler",
    "load_settings",
]

__version__ = "0.1.0"

_STRUCTLOG_CONFIGURED = False


def bootstrap_logging(level: int | str | None = "INFO") -> None:
    """Initialise a basic logging configuration for the CLI entrypoints."""

    if isinstance(level, str):
        level = level.upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    global _STRUCTLOG_CONFIGURED
    if not _STRUCTLOG_CONFIGURED:
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.StackInfoRenderer(),
                structlog.processors.dict_tracebacks,
                structlog.processors.JSONRenderer(),
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        _STRUCTLOG_CONFIGURED = True
