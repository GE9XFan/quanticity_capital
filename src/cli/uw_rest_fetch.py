"""CLI entry point for Unusual Whales REST data fetching.

Run with: python -m src.cli.uw_rest_fetch
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

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

    print("=" * 60)


async def main():
    """Main entry point for the CLI."""
    print("Unusual Whales REST Data Fetcher")
    print("-" * 40)

    # Setup logging
    setup_logging(level="INFO")

    # Validate settings
    if not validate_settings():
        sys.exit(1)

    # Confirm before running
    settings = get_settings()
    print(f"\nReady to fetch data for: {', '.join(settings.symbols)}")
    print(f"This will make approximately {len(settings.symbols) * 30 + 10} API requests.")

    try:
        # Run ingestion
        print("\nStarting ingestion...")
        results = await run_ingestion()

        # Print summary
        print_summary(results)

        # Exit code based on success
        if results["stats"]["failed_requests"] == 0:
            print("\n✅ All requests completed successfully!")
            sys.exit(0)
        else:
            print(f"\n⚠️ {results['stats']['failed_requests']} requests failed. Check logs for details.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nIngestion interrupted by user.")
        sys.exit(130)
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())