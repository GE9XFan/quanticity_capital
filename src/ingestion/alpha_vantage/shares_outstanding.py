"""Fetch and persist the Alpha Vantage SHARES_OUTSTANDING endpoint."""

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

ENDPOINT_SLUG = "shares_outstanding"


def _validate_data(payload: Mapping[str, object]) -> None:
    data = payload.get("data")
    if not data or not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
        raise PayloadValidationError(
            "SHARES_OUTSTANDING payload missing data",
            reason="missing-data",
            extra={"available_keys": list(payload.keys())},
        )

    if len(data) > 0:
        sample = data[0]
        if not isinstance(sample, Mapping):
            raise PayloadValidationError(
                "SHARES_OUTSTANDING data entry is not a mapping",
                reason="malformed-data",
                extra={},
            )

        # Check for key fields that should be present
        required_keys = {"date"}
        # At least one of these should be present
        share_fields = {"shares_outstanding_diluted", "shares_outstanding_basic"}

        missing_required = sorted(required_keys - set(sample))
        if missing_required:
            raise PayloadValidationError(
                "SHARES_OUTSTANDING data missing required fields",
                reason="missing-fields",
                extra={"missing": missing_required},
            )

        if not any(field in sample for field in share_fields):
            raise PayloadValidationError(
                "SHARES_OUTSTANDING data missing share count fields",
                reason="missing-share-fields",
                extra={"expected_one_of": list(share_fields)},
            )


def _validate_payload(payload: Mapping[str, object], symbol: str) -> Mapping[str, object]:
    payload_symbol = payload.get("symbol")
    if payload_symbol and str(payload_symbol).upper() != symbol.upper():
        raise PayloadValidationError(
            "SHARES_OUTSTANDING payload symbol mismatch",
            reason="symbol-mismatch",
            extra={"payload_symbol": payload_symbol, "requested_symbol": symbol},
        )

    # Check for status field if present
    status = payload.get("status")
    if status and status != "success":
        raise PayloadValidationError(
            "SHARES_OUTSTANDING API returned non-success status",
            reason="api-error",
            extra={"status": status},
        )

    _validate_data(payload)
    return payload


_RUNNER = AlphaVantageIngestionRunner(slug=ENDPOINT_SLUG, validator=_validate_payload)


async def run(symbols: Iterable[str] | None = None) -> None:
    await _RUNNER.run(symbols)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Alpha Vantage shares outstanding data")
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
