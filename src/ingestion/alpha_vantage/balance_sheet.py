"""Fetch and persist the Alpha Vantage BALANCE_SHEET endpoint."""

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

ENDPOINT_SLUG = "balance_sheet"


def _validate_reports(payload: Mapping[str, object], key: str) -> None:
    reports = payload.get(key)
    if not reports or not isinstance(reports, Sequence) or isinstance(reports, (str, bytes)):
        raise PayloadValidationError(
            "BALANCE_SHEET payload missing reports",
            reason=f"missing-{key}",
            extra={"reports": key},
        )

    sample = reports[0]
    if not isinstance(sample, Mapping):
        raise PayloadValidationError(
            "BALANCE_SHEET report entry is not a mapping",
            reason="malformed-report",
            extra={"reports": key},
        )

    required_keys = {"fiscalDateEnding", "totalAssets"}
    missing = sorted(required_keys - set(sample))
    if missing:
        raise PayloadValidationError(
            "BALANCE_SHEET report missing required fields",
            reason="missing-fields",
            extra={"missing": missing, "reports": key},
        )


def _validate_payload(payload: Mapping[str, object], symbol: str) -> Mapping[str, object]:
    payload_symbol = payload.get("symbol")
    if payload_symbol and str(payload_symbol).upper() != symbol.upper():
        raise PayloadValidationError(
            "BALANCE_SHEET payload symbol mismatch",
            reason="symbol-mismatch",
            extra={"payload_symbol": payload_symbol, "requested_symbol": symbol},
        )

    _validate_reports(payload, "annualReports")
    _validate_reports(payload, "quarterlyReports")
    return payload


_RUNNER = AlphaVantageIngestionRunner(slug=ENDPOINT_SLUG, validator=_validate_payload)


async def run(symbols: Iterable[str] | None = None) -> None:
    await _RUNNER.run(symbols)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Alpha Vantage balance sheet data")
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
