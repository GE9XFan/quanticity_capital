"""Fetch and persist the Alpha Vantage FEDERAL_FUNDS_RATE macro series."""

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

ENDPOINT_SLUG = "federal_funds_rate"


def _validate_payload(payload: Mapping[str, object], symbol: str) -> Mapping[str, object]:
    if "name" not in payload:
        raise PayloadValidationError(
            "FEDERAL_FUNDS_RATE payload missing name",
            reason="missing-name",
            extra={"keys": list(payload.keys())},
        )

    data = payload.get("data")
    if not data or not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
        raise PayloadValidationError(
            "FEDERAL_FUNDS_RATE payload missing data series",
            reason="missing-data",
            extra={},
        )

    sample = data[0]
    if not isinstance(sample, Mapping):
        raise PayloadValidationError(
            "FEDERAL_FUNDS_RATE data entry is not a mapping",
            reason="malformed-entry",
            extra={},
        )

    required_keys = {"date", "value"}
    missing = sorted(required_keys - set(sample))
    if missing:
        raise PayloadValidationError(
            "FEDERAL_FUNDS_RATE data entry missing required fields",
            reason="missing-fields",
            extra={"missing": missing},
        )

    return payload


_RUNNER = AlphaVantageIngestionRunner(slug=ENDPOINT_SLUG, validator=_validate_payload)


async def run(symbols: Iterable[str] | None = None) -> None:
    await _RUNNER.run(symbols)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Alpha Vantage federal funds rate data")
    parser.add_argument(
        "--symbol",
        dest="symbols",
        action="append",
        help="Optional symbol filter (macro endpoints default to configured entries)",
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
