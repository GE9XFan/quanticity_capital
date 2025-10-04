"""CLI entrypoint for the ingestion worker."""

from __future__ import annotations

import asyncio
import logging

from .service import IngestionService


def configure_logging() -> None:
    """Configure basic structured logging for the worker."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> None:
    """Entrypoint for running the ingestion service."""

    configure_logging()
    service = IngestionService()
    try:
        asyncio.run(service.run_forever())
    except KeyboardInterrupt:  # pragma: no cover - manual shutdown
        logging.getLogger(__name__).info("Ingestion worker interrupted by user")


if __name__ == "__main__":  # pragma: no cover - module execution guard
    main()
