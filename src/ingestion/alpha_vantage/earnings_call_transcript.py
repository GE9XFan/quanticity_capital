"""Fetch and persist Alpha Vantage earnings call transcripts."""

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

ENDPOINT_SLUG = "earnings_call_transcript"


def _validate_payload(payload: Mapping[str, object], symbol: str) -> Mapping[str, object]:
    payload_symbol = payload.get("symbol")
    if payload_symbol and str(payload_symbol).upper() != symbol.upper():
        raise PayloadValidationError(
            "Transcript payload symbol mismatch",
            reason="symbol-mismatch",
            extra={"payload_symbol": payload_symbol, "requested_symbol": symbol},
        )

    # Check for quarter field
    if "quarter" not in payload:
        raise PayloadValidationError(
            "Transcript payload missing quarter field",
            reason="missing-quarter",
            extra={"available_keys": list(payload.keys())},
        )

    # Alpha Vantage returns data in "transcript" field as an array
    transcript = payload.get("transcript")
    if not transcript:
        raise PayloadValidationError(
            "Transcript payload missing transcript data",
            reason="missing-transcript",
            extra={"available_keys": list(payload.keys())},
        )

    if not isinstance(transcript, Sequence) or isinstance(transcript, (str, bytes)):
        raise PayloadValidationError(
            "Transcript field must be an array",
            reason="invalid-transcript-type",
            extra={"transcript_type": type(transcript).__name__},
        )

    # Check structure of transcript entries
    if len(transcript) > 0:
        sample = transcript[0]
        if not isinstance(sample, Mapping):
            raise PayloadValidationError(
                "Transcript entry is not a mapping",
                reason="malformed-transcript-entry",
                extra={},
            )

        # Each transcript entry should have speaker and content
        required_keys = {"speaker", "content"}
        missing = sorted(required_keys - set(sample))
        if missing:
            raise PayloadValidationError(
                "Transcript entry missing required fields",
                reason="missing-fields",
                extra={"missing": missing},
            )

    quarter_value = payload.get("quarter")
    if isinstance(quarter_value, str) and quarter_value:
        if "Q" not in quarter_value:
            raise PayloadValidationError(
                "Transcript quarter not in expected format",
                reason="invalid-quarter",
                extra={"quarter": quarter_value},
            )

    return payload


_RUNNER = AlphaVantageIngestionRunner(slug=ENDPOINT_SLUG, validator=_validate_payload)


async def run(
    symbols: Iterable[str] | None = None,
    *,
    quarter: str | None = None,
) -> None:
    overrides = {}
    if quarter is not None:
        overrides["quarter"] = str(quarter)
    await _RUNNER.run(
        symbols,
        request_param_overrides=overrides or None,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Alpha Vantage earnings call transcripts",
    )
    parser.add_argument(
        "--symbol",
        dest="symbols",
        action="append",
        help="Limit ingestion to specific symbols (repeatable)",
    )
    parser.add_argument(
        "--quarter",
        help="Override transcript quarter (e.g. 2025Q3)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    asyncio.run(
        run(
            args.symbols,
            quarter=args.quarter,
        )
    )


__all__ = [
    "ConfigurationError",
    "build_storage_record",
    "parse_args",
    "run",
]


if __name__ == "__main__":
    main()
