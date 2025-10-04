"""CLI entry point for Unusual Whales REST data fetching."""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from src.config.settings import get_settings
from src.ingestion.rest_runner import run_ingestion


def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging for the CLI.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Generate log filename with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"unusual_whales_rest_{timestamp}.log"

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Set specific levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_file}")


def validate_settings() -> bool:
    """Validate required settings are present.

    Returns:
        True if settings are valid, False otherwise
    """
    try:
        settings = get_settings()

        if not settings.unusual_whales_api_token:
            logging.error("UNUSUAL_WHALES_API_TOKEN is not set!")
            logging.error("Please set it in your .env file or environment variables")
            return False

        if not settings.symbols:
            logging.error("No target symbols configured!")
            return False

        # Log configuration
        logger = logging.getLogger(__name__)
        logger.info("Configuration loaded successfully:")
        logger.info(f"  Environment: {settings.environment}")
        logger.info(f"  Target symbols: {', '.join(settings.symbols)}")
        logger.info(f"  Rate limit: {settings.rate_limit_requests_per_minute} req/min")
        logger.info(f"  Request timeout: {settings.request_timeout_seconds}s")
        logger.info(f"  Store to Redis: {settings.store_to_redis}")
        logger.info(f"  Loop interval (settings): {settings.fetch_interval_seconds}s")

        return True

    except Exception as e:
        logging.error(f"Failed to load settings: {e}")
        return False


def print_summary(results: dict) -> None:
    """Print a summary of the ingestion run.

    Args:
        results: Results dictionary from ingestion runner
    """
    stats = results["stats"]
    saved_files = results["saved_files"]
    errors = results["errors"]

    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)

    # Time stats
    duration = (stats["end_time"] - stats["start_time"]).total_seconds()
    print(f"Duration: {duration:.2f} seconds")
    print(f"Start: {stats['start_time'].isoformat()}")
    print(f"End: {stats['end_time'].isoformat()}")

    # Request stats
    print(f"\nRequests:")
    print(f"  Total: {stats['total_requests']}")
    print(f"  Successful: {stats['successful_requests']}")
    print(f"  Failed: {stats['failed_requests']}")
    success_rate = (
        (stats['successful_requests'] / stats['total_requests'] * 100)
        if stats['total_requests'] > 0 else 0
    )
    print(f"  Success rate: {success_rate:.1f}%")

    # File stats
    print(f"\nSaved files: {len([f for f in saved_files if f is not None])}")
    print(f"Unique endpoints processed: {len(stats['endpoints_processed'])}")
    print(f"Redis snapshots successful: {stats['redis_success']}")
    print(f"Redis snapshot failures: {stats['redis_failures']}")
    print(f"Postgres writes successful: {stats['postgres_success']}")
    print(f"Postgres write failures: {stats['postgres_failures']}")

    # Errors summary
    if errors:
        print(f"\nErrors ({len(errors)}):")
        # Group errors by type
        error_counts = {}
        for error in errors:
            error_key = f"{error.get('endpoint')}:{error.get('status_code', 'unknown')}"
            error_counts[error_key] = error_counts.get(error_key, 0) + 1

        for error_key, count in sorted(error_counts.items()):
            print(f"  {error_key}: {count} occurrence(s)")

    # Data location
    print(f"\nData saved to: data/unusual_whales/raw/")
    print("Redis keys prefix: uw:rest:<endpoint>[:<symbol>]")

    print("=" * 60)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Unusual Whales REST endpoints")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously using the configured interval",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help="Loop interval in seconds (overrides FETCH_INTERVAL_SECONDS)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Run the loop for a fixed number of iterations",
    )
    return parser.parse_args()


async def run_once() -> Dict[str, Any]:
    results = await run_ingestion()
    print_summary(results)
    return results


async def main() -> None:
    args = parse_args()

    print("Unusual Whales REST Data Fetcher")
    print("-" * 40)

    setup_logging(level="INFO")

    if not validate_settings():
        sys.exit(1)

    settings = get_settings()
    print(f"\nReady to fetch data for: {', '.join(settings.symbols)}")
    print(f"This will make approximately {len(settings.symbols) * 30 + 10} API requests per run.")

    interval = args.interval if args.interval is not None else settings.fetch_interval_seconds
    loop_mode = args.loop or interval > 0
    if args.loop and interval <= 0:
        interval = 900.0
        logging.getLogger(__name__).warning(
            "Loop requested but FETCH_INTERVAL_SECONDS not set. Defaulting interval to %ss.", interval
        )

    try:
        iteration = 0
        while True:
            iteration += 1
            if loop_mode:
                print(f"\nIteration {iteration}")

            results = await run_once()
            stats = results["stats"]
            has_failures = stats["failed_requests"] > 0 or stats["redis_failures"] > 0

            if not loop_mode:
                if not has_failures:
                    print("\n✅ All requests completed successfully!")
                    sys.exit(0)
                print("\n⚠️ Some requests or Redis writes failed. Check logs for details.")
                sys.exit(1)

            if args.max_iterations and iteration >= args.max_iterations:
                print("\nReached max iterations. Exiting loop.")
                sys.exit(0 if not has_failures else 1)

            duration = (stats["end_time"] - stats["start_time"]).total_seconds()
            sleep_time = max(interval - duration, 0)
            print(f"\nSleeping {sleep_time:.2f}s before next cycle...")
            await asyncio.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n\nIngestion interrupted by user.")
        sys.exit(130)
    except Exception as exc:
        logging.error("Unexpected error", exc_info=True)
        print(f"\n❌ Fatal error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
