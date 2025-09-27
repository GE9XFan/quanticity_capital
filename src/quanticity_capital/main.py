"""Command line interface scaffold for the Quanticity Capital platform."""

from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path
from typing import Callable, Optional, Sequence

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency guard
    load_dotenv = None  # type: ignore[assignment]

from . import (
    AlphaVantageOrchestrator,
    AlphaVantageScheduler,
    bootstrap_logging,
    load_settings,
    __version__,
)


Handler = Callable[[argparse.Namespace], int]

_LOADED_ENV_PATHS: set[Path] = set()
_DEFAULT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def bootstrap_env() -> None:
    """Load environment variables from a `.env` file when available."""

    if load_dotenv is None:
        return

    logger = logging.getLogger("quanticity_capital.cli.env")
    env_hint = os.environ.get("QUANTICITY_ENV_FILE")
    candidates: tuple[Path, ...]
    if env_hint:
        candidates = (Path(env_hint), _DEFAULT_ENV_PATH)
    else:
        candidates = (_DEFAULT_ENV_PATH,)

    for candidate in candidates:
        if not candidate:
            continue
        if candidate.is_file():
            if candidate not in _LOADED_ENV_PATHS:
                load_dotenv(candidate, override=False)
                _LOADED_ENV_PATHS.add(candidate)
                logger.debug("Loaded environment variables from %s", candidate)
            break


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

    subparsers = parser.add_subparsers(dest="command")

    ingest_parser = subparsers.add_parser("ingest", help="Run ingestion workflows")
    ingest_subparsers = ingest_parser.add_subparsers(dest="integration")

    alpha_parser = ingest_subparsers.add_parser(
        "alpha-vantage",
        help="Dispatch Alpha Vantage jobs using the configured orchestrator.",
    )
    alpha_parser.add_argument(
        "--settings",
        default=None,
        help="Optional path to settings YAML (defaults to repository configuration)",
    )
    alpha_parser.add_argument(
        "--endpoint",
        dest="endpoints",
        action="append",
        help="Limit dispatch to the specified endpoint (repeat for multiples)",
    )
    alpha_parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help="Seconds between successive dispatch loops; omit to run once",
    )
    alpha_parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum dispatch iterations when --interval is set",
    )
    alpha_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the job plan without executing any API calls",
    )
    alpha_parser.add_argument(
        "--api-key",
        dest="api_key",
        default=None,
        help="Alpha Vantage API key override (otherwise read from environment)",
    )
    alpha_parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run a persistent scheduler that respects trading hours and Redis TTL guardrails",
    )
    alpha_parser.add_argument(
        "--refresh-guard-seconds",
        type=int,
        default=120,
        help="Minimum remaining TTL before a job is re-run when --schedule is enabled",
    )
    alpha_parser.set_defaults(handler=run_alpha_vantage_ingest)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    bootstrap_logging(args.log_level)
    bootstrap_env()
    logger = logging.getLogger("quanticity_capital.cli")
    handler: Optional[Handler] = getattr(args, "handler", None)

    if handler is None:
        logger.info("Quanticity Capital repository skeleton is ready.")
        return 0

    try:
        return handler(args)
    except KeyboardInterrupt:  # pragma: no cover - user abort
        logger.warning("Operation interrupted by user")
        return 130


def run_alpha_vantage_ingest(args: argparse.Namespace) -> int:
    logger = logging.getLogger("quanticity_capital.cli.alpha_vantage")

    settings = load_settings(args.settings)
    services_cfg = settings.get("services", {}).get("alphavantage", {})
    api_key_env = services_cfg.get("api_key_env", "ALPHAVANTAGE_API_KEY")

    env = dict(os.environ)
    if args.api_key:
        env[api_key_env] = args.api_key

    if api_key_env not in env or not env[api_key_env]:
        raise RuntimeError(
            f"Alpha Vantage orchestrator requires environment variable '{api_key_env}' or --api-key"
        )

    if args.schedule and args.dry_run:
        raise RuntimeError("--schedule cannot be combined with --dry-run")

    orchestrator = AlphaVantageOrchestrator(
        settings=settings,
        env=env,
        enabled_endpoints=args.endpoints,
        persist_results=(not args.dry_run) or args.schedule,
    )

    try:
        plan = orchestrator.build_job_plan()
        total_jobs = sum(len(jobs) for jobs in plan.values())
        logger.info(
            "Alpha Vantage job plan prepared: %d endpoints / %d jobs",
            len(plan),
            total_jobs,
        )

        if args.dry_run:
            return 0

        if args.schedule:
            poll_interval = args.interval if args.interval is not None else 60.0
            if poll_interval <= 0:
                raise RuntimeError("--interval must be positive when --schedule is enabled")
            scheduler = AlphaVantageScheduler(
                orchestrator,
                poll_interval=poll_interval,
                refresh_guard_seconds=args.refresh_guard_seconds,
            )
            logger.info(
                "Starting Alpha Vantage scheduler (poll %.0fs, refresh guard %ds)",
                poll_interval,
                args.refresh_guard_seconds,
            )
            scheduler.run_forever()
            return 0

        iterations = 0
        interval = args.interval
        max_iterations = args.max_iterations

        while True:
            iterations += 1
            results = orchestrator.dispatch()
            ok = sum(1 for result in results if result.status == "ok")
            errors = len(results) - ok
            logger.info(
                "Alpha Vantage dispatch #%d complete: %d ok / %d error",
                iterations,
                ok,
                errors,
            )

            if max_iterations is not None and iterations >= max_iterations:
                break
            if interval is None:
                break
            if interval <= 0:
                logger.warning("Interval %.2fs is non-positive; stopping after single iteration", interval)
                break
            logger.debug("Sleeping for %.2f seconds before next dispatch", interval)
            time.sleep(interval)

        return 0
    finally:
        orchestrator.close()


if __name__ == "__main__":  # pragma: no cover - direct execution helper
    raise SystemExit(main())
