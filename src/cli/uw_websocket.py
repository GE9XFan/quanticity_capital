"""CLI entry point for the Unusual Whales WebSocket consumer."""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

from src.config.settings import get_settings
from src.websocket.uw_consumer import run_websocket_consumer


def setup_logging(level: str = "INFO") -> None:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"uw_websocket_{timestamp}.log"

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger(__name__).info("Logging initialised. Log file: %s", log_file)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Unusual Whales WebSocket consumer")
    parser.add_argument("--log-level", default="INFO", help="Logging level (default: INFO)")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    setup_logging(args.log_level)

    settings = get_settings()
    if not settings.enable_websocket:
        logging.getLogger(__name__).warning(
            "ENABLE_WEBSOCKET is false. Set it to true in .env to start the consumer."
        )
        return

    try:
        await run_websocket_consumer()
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("WebSocket consumer interrupted by user")


if __name__ == "__main__":
    asyncio.run(main())
