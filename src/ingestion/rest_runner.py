"""REST ingestion runner for Unusual Whales data."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src.clients.redis_store import RedisStore, create_store
from src.clients.unusual_whales import UnusualWhalesClient
from src.config.settings import get_settings
from src.ingestion.uw_endpoints import GLOBAL_ENDPOINTS, TICKER_ENDPOINTS

logger = logging.getLogger(__name__)


class RestIngestionRunner:
    """Coordinate REST ingestion, disk persistence, and Redis snapshots."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.settings = get_settings()
        self.data_dir = data_dir or Path("data/unusual_whales/raw")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.stats: Dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "endpoints_processed": set(),
            "start_time": None,
            "end_time": None,
            "redis_success": 0,
            "redis_failures": 0,
        }
        self.redis_store: Optional[RedisStore] = None

    async def run(self) -> Dict[str, Any]:
        """Fetch all configured endpoints once."""

        self.stats["start_time"] = datetime.utcnow()
        logger.info("Starting REST ingestion run at %s", self.stats["start_time"])
        symbols = self.settings.symbols
        logger.info("Target symbols: %s", symbols)

        results: Dict[str, Any] = {
            "stats": self.stats,
            "saved_files": [],
            "errors": [],
        }

        self.redis_store = await create_store(self.settings, self.settings.store_to_redis)

        try:
            async with UnusualWhalesClient() as client:
                # Global endpoints first
                logger.info("Fetching %d global endpoints...", len(GLOBAL_ENDPOINTS))
                for endpoint in GLOBAL_ENDPOINTS:
                    result = await self._fetch_persist(client, endpoint, ticker=None)
                    self._record_result(results, result)

                # Ticker endpoints
                logger.info(
                    "Fetching %d endpoints for %d symbols...",
                    len(TICKER_ENDPOINTS),
                    len(symbols),
                )
                for symbol in symbols:
                    logger.info("Processing symbol: %s", symbol)
                    for endpoint in TICKER_ENDPOINTS:
                        result = await self._fetch_persist(client, endpoint, ticker=symbol)
                        self._record_result(results, result)
        finally:
            if self.redis_store is not None:
                await self.redis_store.close()
                self.redis_store = None

        self.stats["end_time"] = datetime.utcnow()
        duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()
        logger.info(
            "Ingestion completed in %.2fs. Success: %s, Failed: %s, Total: %s, Redis ok: %s, Redis errors: %s",
            duration,
            self.stats["successful_requests"],
            self.stats["failed_requests"],
            self.stats["total_requests"],
            self.stats["redis_success"],
            self.stats["redis_failures"],
        )

        return results

    async def _fetch_persist(self, client: UnusualWhalesClient, endpoint, ticker: Optional[str]) -> Dict[str, Any]:
        identifier = f"{endpoint.key}" + (f":{ticker}" if ticker else "")
        logger.debug("Fetching %s", identifier)

        try:
            response = await client.fetch_endpoint(endpoint, ticker=ticker)
        except Exception as exc:  # catch unexpected issues
            logger.error("✗ %s: unexpected error: %s", identifier, exc, exc_info=True)
            return {
                "success": False,
                "endpoint": endpoint.key,
                "ticker": ticker,
                "error": str(exc),
            }

        if not response["success"]:
            logger.error(
                "✗ %s: %s (status: %s)",
                identifier,
                response.get("error", "Unknown error"),
                response.get("status_code", "N/A"),
            )
            return {
                "success": False,
                "endpoint": endpoint.key,
                "ticker": ticker,
                "error": response.get("error"),
                "status_code": response.get("status_code"),
            }

        # Persist to disk
        metadata = {
            "status_code": response["status_code"],
            "timestamp": response["timestamp"],
            "endpoint": endpoint.key,
            "ticker": ticker,
        }
        file_path = self._save_response(endpoint.key, ticker, response["data"], metadata)

        # Optional Redis snapshot
        redis_key = None
        if self.redis_store is not None:
            try:
                redis_key = await self.redis_store.write_snapshot(
                    endpoint=endpoint.key,
                    ticker=ticker,
                    payload=response["data"],
                    fetched_at=datetime.utcnow().isoformat(),
                )
                self.stats["redis_success"] += 1
            except Exception as redis_error:
                self.stats["redis_failures"] += 1
                logger.error(
                    "Redis write failed for %s: %s",
                    identifier,
                    redis_error,
                    exc_info=True,
                )

        logger.info("✓ %s → %s", identifier, file_path)
        return {
            "success": True,
            "endpoint": endpoint.key,
            "ticker": ticker,
            "file_path": str(file_path),
            "redis_key": redis_key,
        }

    def _save_response(
        self,
        endpoint_key: str,
        ticker: Optional[str],
        data: Any,
        metadata: Dict[str, Any],
    ) -> Path:
        endpoint_dir = self.data_dir / endpoint_key
        endpoint_dir.mkdir(exist_ok=True)

        timestamp = datetime.utcnow().isoformat().replace(":", "-").replace(".", "-")
        filename = f"{ticker}_{timestamp}.json" if ticker else f"{timestamp}.json"
        file_path = endpoint_dir / filename

        save_data = {
            "metadata": {
                **metadata,
                "saved_at": datetime.utcnow().isoformat(),
                "endpoint_key": endpoint_key,
            },
            "data": data,
        }
        with open(file_path, "w") as handle:
            json.dump(save_data, handle, indent=2, default=str)

        self._update_index(endpoint_key, ticker, file_path, metadata)
        return file_path

    def _update_index(
        self,
        endpoint_key: str,
        ticker: Optional[str],
        file_path: Path,
        metadata: Dict[str, Any],
    ) -> None:
        index_path = self.data_dir / endpoint_key / "index.ndjson"
        index_entry = {
            "file": file_path.name,
            "ticker": ticker,
            "fetched_at": datetime.utcnow().isoformat(),
            "status_code": metadata.get("status_code"),
            "timestamp": metadata.get("timestamp"),
        }
        with open(index_path, "a") as handle:
            handle.write(json.dumps(index_entry) + "\n")

    def _record_result(self, results: Dict[str, Any], result: Dict[str, Any]) -> None:
        if result["success"]:
            results["saved_files"].append(result.get("file_path"))
        else:
            results["errors"].append(result)
        self._update_stats(result)

    def _update_stats(self, result: Dict[str, Any]) -> None:
        self.stats["total_requests"] += 1
        if result["success"]:
            self.stats["successful_requests"] += 1
        else:
            self.stats["failed_requests"] += 1

        endpoint_key = result["endpoint"]
        if result.get("ticker"):
            endpoint_key = f"{endpoint_key}:{result['ticker']}"
        self.stats["endpoints_processed"].add(endpoint_key)


async def run_ingestion(data_dir: Optional[Path] = None) -> Dict[str, Any]:
    runner = RestIngestionRunner(data_dir)
    return await runner.run()
