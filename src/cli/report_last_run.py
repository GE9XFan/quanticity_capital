"""Quick health report for the latest REST ingestion run."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import asyncpg
import redis

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class EndpointReport:
    endpoint: str
    latest_file: Optional[Path]
    latest_timestamp: Optional[str]
    redis_snapshot: Optional[str]
    redis_stream_len: Optional[int]
    postgres_rows_last_hour: Optional[int]


HISTORY_ENDPOINTS = {
    "flow_alerts",
    "net_prem_ticks",
    "nope",
    "ohlc_1m",
    "options_volume",
}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Show summary of latest REST run")
    parser.add_argument("--data-dir", default="data/unusual_whales/raw", help="Root of raw data archive")
    parser.add_argument("--limit", type=int, default=5, help="Number of endpoints to show")
    args = parser.parse_args()

    settings = get_settings()
    data_dir = Path(args.data_dir)

    if not data_dir.exists():
        logger.error("Data directory %s not found", data_dir)
        return

    redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    postgres_conn: Optional[asyncpg.Connection] = None
    if settings.store_to_postgres:
        postgres_conn = run_async(asyncpg.connect(settings.postgres_dsn))

    try:
        endpoints = sorted(p for p in data_dir.iterdir() if p.is_dir())
        print("REST RUN HEALTH CHECK")
        print("======================")

        for endpoint_path in endpoints[: args.limit]:
            endpoint = endpoint_path.name
            report = build_endpoint_report(endpoint_path, endpoint, redis_client, postgres_conn)
            print_endpoint_report(report)
    finally:
        if postgres_conn is not None:
            run_async(postgres_conn.close())


def build_endpoint_report(
    endpoint_path: Path,
    endpoint: str,
    redis_client: redis.Redis,
    postgres_conn: Optional[asyncpg.Connection],
) -> EndpointReport:
    latest_file = get_latest_file(endpoint_path)
    latest_timestamp = extract_timestamp(latest_file)

    redis_key = f"uw:rest:{endpoint}"
    redis_snapshot = redis_client.hget(redis_key, "fetched_at")

    stream_key = f"uw:rest:{endpoint}:stream"
    redis_stream_len = redis_client.xlen(stream_key) if redis_client.exists(stream_key) else None

    postgres_rows_last_hour = None
    if postgres_conn is not None and endpoint in HISTORY_ENDPOINTS:
        query = """
            SELECT COUNT(1) FROM uw_rest_history
            WHERE endpoint = $1 AND fetched_at > NOW() - INTERVAL '1 hour'
        """
        postgres_rows_last_hour = run_async(postgres_conn.fetchval(query, endpoint))

    return EndpointReport(
        endpoint=endpoint,
        latest_file=latest_file,
        latest_timestamp=latest_timestamp,
        redis_snapshot=redis_snapshot,
        redis_stream_len=redis_stream_len,
        postgres_rows_last_hour=postgres_rows_last_hour,
    )


def get_latest_file(endpoint_path: Path) -> Optional[Path]:
    files = sorted(endpoint_path.glob("*.json"), reverse=True)
    return files[0] if files else None


def extract_timestamp(latest_file: Optional[Path]) -> Optional[str]:
    if latest_file is None:
        return None
    try:
        with latest_file.open() as handle:
            data = json.load(handle)
        return data.get("metadata", {}).get("timestamp")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not parse %s: %s", latest_file, exc)
        return None


def print_endpoint_report(report: EndpointReport) -> None:
    print(f"Endpoint: {report.endpoint}")
    print(f"  Latest file: {report.latest_file}")
    print(f"  Last REST timestamp: {report.latest_timestamp}")
    print(f"  Redis snapshot fetched_at: {report.redis_snapshot}")
    if report.redis_stream_len is not None:
        print(f"  Redis stream length: {report.redis_stream_len}")
    if report.postgres_rows_last_hour is not None:
        print(f"  Postgres rows (last hour): {report.postgres_rows_last_hour}")
    print()


def run_async(coro):
    try:
        import asyncio

        loop = asyncio.get_event_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        if loop.is_running():
            return asyncio.run(coro)
        return loop.run_until_complete(coro)


if __name__ == "__main__":
    main()
