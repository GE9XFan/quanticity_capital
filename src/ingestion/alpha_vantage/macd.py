"""Fetch and persist the Alpha Vantage MACD endpoint."""

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

ENDPOINT_SLUG = "macd"


def _validate_payload(payload: Mapping[str, object], symbol: str) -> Mapping[str, object]:
    analysis_key = next((key for key in payload if key.lower().startswith("technical analysis")), None)
    analysis = payload.get(analysis_key) if analysis_key else None
    if not analysis or not isinstance(analysis, Mapping):
        raise PayloadValidationError(
            "MACD payload missing technical analysis section",
            reason="missing-technical-analysis",
            extra={"keys": list(payload.keys())},
        )

    first_key = next(iter(analysis), None)
    if not first_key:
        raise PayloadValidationError(
            "MACD payload provided empty technical analysis",
            reason="empty-technical-analysis",
            extra={},
        )

    first_entry = analysis[first_key]
    if not isinstance(first_entry, Mapping):
        raise PayloadValidationError(
            "MACD payload entry is not a mapping",
            reason="malformed-macd-entry",
            extra={},
        )

    required_keys = {"MACD", "MACD_Signal", "MACD_Hist"}
    missing = sorted(required_keys - set(first_entry))
    if missing:
        raise PayloadValidationError(
            "MACD payload missing expected components",
            reason="missing-macd-components",
            extra={"missing": missing},
        )

    return payload


_RUNNER = AlphaVantageIngestionRunner(slug=ENDPOINT_SLUG, validator=_validate_payload)


async def run(symbols: Iterable[str] | None = None) -> None:
    await _RUNNER.run(symbols)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Alpha Vantage MACD data")
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
