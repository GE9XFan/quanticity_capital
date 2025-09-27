"""Command line interface scaffold for the Quanticity Capital platform."""

from __future__ import annotations

import argparse
import logging
from typing import Sequence

from . import bootstrap_logging, __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bootstrap the Quanticity Capital data platform CLI.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Log level for bootstrap logging (default: INFO)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"quanticity-capital {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    bootstrap_logging(args.log_level)
    logger = logging.getLogger("quanticity_capital.cli")
    logger.info("Quanticity Capital repository skeleton is ready.")

    return 0


if __name__ == "__main__":  # pragma: no cover - direct execution helper
    raise SystemExit(main())
