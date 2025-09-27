"""Primary CLI entry point for the Quanticity Capital runtime."""
from __future__ import annotations

import argparse
from typing import Optional

import structlog
from dotenv import load_dotenv
from redis.exceptions import RedisError

from src.core.config import RuntimeSettings, load_runtime_config
from src.core.logging import configure_logging
from src.core.redis import create_client
from src.ingestion.scheduler import IngestionScheduler


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quanticity Capital runtime")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load configuration and exit without starting services.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    load_dotenv()
    config = load_runtime_config()
    settings = RuntimeSettings.from_config(config)

    configure_logging(settings.log_level)
    logger = structlog.get_logger(__name__)

    if args.dry_run:
        logger.info(
            "runtime_dry_run",
            redis_url=settings.redis_url,
            features=settings.features.as_dict(),
            analytics=settings.analytics.as_dict(),
        )
        return 0

    redis_client = create_client(settings.redis_url)
    try:
        redis_client.ping()
    except RedisError as exc:  # pragma: no cover - depends on local Redis availability
        logger.warning("redis_ping_failed", error=str(exc))
    else:
        logger.info("redis_ping_succeeded")

    if settings.features.scheduler:
        scheduler = IngestionScheduler(
            redis_client=redis_client,
            logger=logger,
            analytics=settings.analytics,
        )
        scheduler.bootstrap()
        scheduler.start()

    logger.info(
        "runtime_bootstrap_complete",
        redis_url=settings.redis_url,
        features=settings.features.as_dict(),
        analytics=settings.analytics.as_dict(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
