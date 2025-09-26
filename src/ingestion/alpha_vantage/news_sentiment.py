"""Fetch and persist the Alpha Vantage NEWS_SENTIMENT endpoint."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Iterable, Mapping, Sequence

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from src.ingestion.alpha_vantage._shared import (
    AlphaVantageIngestionRunner,
    ConfigurationError,
    PayloadValidationError,
    build_storage_record,
)

ENDPOINT_SLUG = "news_sentiment"


def _validate_payload(payload: Mapping[str, object], symbol: str) -> Mapping[str, object]:
    feed = payload.get("feed")
    if not feed or not isinstance(feed, Sequence) or isinstance(feed, (str, bytes)):
        raise PayloadValidationError(
            "NEWS_SENTIMENT payload missing 'feed' array",
            reason="missing-feed",
            extra={"keys": list(payload.keys()), "feed_count": len(feed) if isinstance(feed, Sequence) else 0},
        )

    sample_entry = feed[0]
    if not isinstance(sample_entry, Mapping):
        raise PayloadValidationError(
            "NEWS_SENTIMENT feed entry is not a mapping",
            reason="malformed-feed-entry",
            extra={},
        )

    required_fields = {"title", "url", "time_published", "overall_sentiment_score", "ticker_sentiment"}
    missing = sorted(required_fields - set(sample_entry))
    if missing:
        raise PayloadValidationError(
            "NEWS_SENTIMENT feed entry missing required fields",
            reason="missing-fields",
            extra={"missing": missing},
        )

    ticker_sentiment = sample_entry.get("ticker_sentiment")
    if not isinstance(ticker_sentiment, Sequence) or isinstance(ticker_sentiment, (str, bytes)):
        raise PayloadValidationError(
            "NEWS_SENTIMENT ticker_sentiment must be a sequence",
            reason="invalid-ticker-sentiment",
            extra={},
        )

    return payload


_RUNNER = AlphaVantageIngestionRunner(slug=ENDPOINT_SLUG, validator=_validate_payload)


async def run(symbols: Iterable[str] | None = None) -> None:
    await _RUNNER.run(symbols)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Alpha Vantage NEWS_SENTIMENT data")
    parser.add_argument(
        "--symbol",
        dest="symbols",
        action="append",
        help="Limit ingestion to specific symbols (repeatable)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    asyncio.run(run(args.symbols))


__all__ = [
    "ConfigurationError",
    "build_storage_record",
    "parse_args",
    "run",
]


if __name__ == "__main__":
    main()
