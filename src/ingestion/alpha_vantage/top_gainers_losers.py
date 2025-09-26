"""Fetch and persist the Alpha Vantage TOP_GAINERS_LOSERS endpoint."""

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

ENDPOINT_SLUG = "top_gainers_losers"


_REQUIRED_SECTIONS = ("top_gainers", "top_losers", "most_actively_traded")


def _validate_payload(payload: Mapping[str, object], symbol: str) -> Mapping[str, object]:
    for section in _REQUIRED_SECTIONS:
        values = payload.get(section)
        if not values or not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            raise PayloadValidationError(
                "TOP_GAINERS_LOSERS payload missing expected section",
                reason=f"missing-{section}",
                extra={"section": section},
            )

    metadata = payload.get("metadata")
    if not metadata:
        raise PayloadValidationError(
            "TOP_GAINERS_LOSERS payload missing metadata",
            reason="missing-metadata",
            extra={},
        )

    return payload


_RUNNER = AlphaVantageIngestionRunner(slug=ENDPOINT_SLUG, validator=_validate_payload)


async def run(symbols: Iterable[str] | None = None) -> None:
    await _RUNNER.run(symbols)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Alpha Vantage TOP_GAINERS_LOSERS data")
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
