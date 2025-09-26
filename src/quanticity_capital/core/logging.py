"""Logging bootstrap utilities."""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path
from typing import Optional

import structlog

from ..config.models import AppConfig

_STRUCTLOG_CONFIGURED = False


def _configure_structlog(level: int) -> None:
    global _STRUCTLOG_CONFIGURED
    if _STRUCTLOG_CONFIGURED:
        return
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.set_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    _STRUCTLOG_CONFIGURED = True
    structlog.get_logger().info("structlog configured", level=level)


def setup_logging(settings: AppConfig) -> structlog.stdlib.BoundLogger:
    """Configure standard logging and return the root structlog logger."""

    runtime_logging = settings.runtime.logging
    level = logging.getLevelName(runtime_logging.level.upper())
    if isinstance(level, str):  # pragma: no cover - defensive fallback
        level = logging.INFO

    config_file: Optional[str] = runtime_logging.config_file
    if config_file:
        path = Path(config_file)
        if not path.is_absolute():
            path = Path.cwd() / path
        if path.exists():
            logging.config.fileConfig(path, disable_existing_loggers=False)
        else:
            logging.basicConfig(
                level=level,
                format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            )
            logging.getLogger(__name__).warning(
                "Logging config file missing; fell back to basicConfig", extra={"path": str(path)}
            )
    else:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )

    _configure_structlog(level)

    logger = structlog.get_logger("quanticity.orchestrator")
    logger.info(
        "logging configured",
        level=logging.getLevelName(level),
        config_file=config_file,
    )
    return logger


__all__ = ["setup_logging"]
