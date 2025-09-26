"""Fetch and persist the Alpha Vantage EARNINGS_ESTIMATES endpoint."""

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

ENDPOINT_SLUG = "earnings_estimates"


def _validate_payload(payload: Mapping[str, object], symbol: str) -> Mapping[str, object]:
    payload_symbol = payload.get("symbol")
    if payload_symbol and str(payload_symbol).upper() != symbol.upper():
        raise PayloadValidationError(
            "EARNINGS_ESTIMATES payload symbol mismatch",
            reason="symbol-mismatch",
            extra={"payload_symbol": payload_symbol, "requested_symbol": symbol},
        )

    # Alpha Vantage returns data in "estimates" field
    estimates = payload.get("estimates")
    if not estimates or not isinstance(estimates, Sequence) or isinstance(estimates, (str, bytes)):
        raise PayloadValidationError(
            "EARNINGS_ESTIMATES payload missing estimates data",
            reason="missing-estimates",
            extra={"available_keys": list(payload.keys())},
        )

    if len(estimates) > 0:
        sample = estimates[0]
        if not isinstance(sample, Mapping):
            raise PayloadValidationError(
                "EARNINGS_ESTIMATES estimates entry is not a mapping",
                reason="malformed-estimates-entry",
                extra={},
            )

        # Check for key fields that should be present
        required_keys = {"date", "horizon", "eps_estimate_average"}
        missing = sorted(required_keys - set(sample))
        if missing:
            raise PayloadValidationError(
                "EARNINGS_ESTIMATES entry missing required fields",
                reason="missing-fields",
                extra={"missing": missing},
            )

    return payload


_RUNNER = AlphaVantageIngestionRunner(slug=ENDPOINT_SLUG, validator=_validate_payload)


async def run(symbols: Iterable[str] | None = None) -> None:
    await _RUNNER.run(symbols)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Alpha Vantage earnings estimates")
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
