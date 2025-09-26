"""Fetch and persist the Alpha Vantage TIME_SERIES_INTRADAY endpoint."""

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

ENDPOINT_SLUG = "time_series_intraday"


def _validate_payload(payload: Mapping[str, object], symbol: str) -> Mapping[str, object]:
    meta = payload.get("Meta Data")
    if not meta or not isinstance(meta, Mapping):
        raise PayloadValidationError(
            "TIME_SERIES_INTRADAY payload missing 'Meta Data' section",
            reason="missing-meta",
            extra={"keys": list(payload.keys())},
        )

    interval = meta.get("4. Interval")
    if not interval:
        raise PayloadValidationError(
            "TIME_SERIES_INTRADAY payload missing interval metadata",
            reason="missing-interval",
            extra={"meta_keys": list(meta.keys())},
        )

    series_key = next((key for key in payload if key.lower().startswith("time series")), None)
    if not series_key:
        raise PayloadValidationError(
            "TIME_SERIES_INTRADAY payload missing time series data",
            reason="missing-time-series",
            extra={"keys": list(payload.keys())},
        )

    series = payload.get(series_key)
    if not isinstance(series, Mapping) or not series:
        raise PayloadValidationError(
            "TIME_SERIES_INTRADAY payload contains empty time series",
            reason="empty-time-series",
            extra={"series_key": series_key},
        )

    first_entry = next(iter(series.values()), None)
    if not isinstance(first_entry, Mapping):
        raise PayloadValidationError(
            "TIME_SERIES_INTRADAY payload entries are not mappings",
            reason="malformed-entry",
            extra={"series_key": series_key},
        )

    required_fields = {"1. open", "2. high", "3. low", "4. close", "5. volume"}
    missing = sorted(required_fields - set(first_entry))
    if missing:
        raise PayloadValidationError(
            "TIME_SERIES_INTRADAY payload missing OHLCV fields",
            reason="missing-ohlcv",
            extra={"missing": missing, "series_key": series_key},
        )

    return payload


_RUNNER = AlphaVantageIngestionRunner(slug=ENDPOINT_SLUG, validator=_validate_payload)


async def run(symbols: Iterable[str] | None = None) -> None:
    await _RUNNER.run(symbols)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Alpha Vantage TIME_SERIES_INTRADAY data")
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
