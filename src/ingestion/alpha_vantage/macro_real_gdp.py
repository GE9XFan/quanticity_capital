"""Fetch and persist the Alpha Vantage REAL_GDP macro series."""

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

ENDPOINT_SLUG = "macro_real_gdp"


def _validate_payload(payload: Mapping[str, object], symbol: str) -> Mapping[str, object]:
    if payload.get("name") != "Real Gross Domestic Product":
        raise PayloadValidationError(
            "REAL_GDP payload missing expected name",
            reason="missing-name",
            extra={"name": payload.get("name")},
        )

    data = payload.get("data")
    if not data or not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
        raise PayloadValidationError(
            "REAL_GDP payload missing data series",
            reason="missing-data",
            extra={"keys": list(payload.keys())},
        )

    sample = data[0]
    if not isinstance(sample, Mapping):
        raise PayloadValidationError(
            "REAL_GDP data entry is not a mapping",
            reason="malformed-entry",
            extra={},
        )

    required_keys = {"date", "value"}
    missing = sorted(required_keys - set(sample))
    if missing:
        raise PayloadValidationError(
            "REAL_GDP data entry missing required fields",
            reason="missing-fields",
            extra={"missing": missing},
        )

    return payload


_RUNNER = AlphaVantageIngestionRunner(slug=ENDPOINT_SLUG, validator=_validate_payload)


async def run(symbols: Iterable[str] | None = None) -> None:
    await _RUNNER.run(symbols)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Alpha Vantage REAL_GDP macro series")
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
