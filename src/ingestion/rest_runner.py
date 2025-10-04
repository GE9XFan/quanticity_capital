"""REST ingestion runner for Unusual Whales data.

Orchestrates fetching all configured endpoints, respecting rate limits,
and saving raw JSON responses to disk.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.clients.unusual_whales import UnusualWhalesClient
from src.config.settings import get_settings
from src.ingestion.uw_endpoints import ENDPOINTS, TICKER_ENDPOINTS, GLOBAL_ENDPOINTS


logger = logging.getLogger(__name__)


class RestIngestionRunner:
    """Orchestrates REST API data ingestion."""

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize the ingestion runner.

        Args:
            data_dir: Base directory for storing raw data.
                      Defaults to data/unusual_whales/raw/
        """
        self.settings = get_settings()
        self.data_dir = data_dir or Path("data/unusual_whales/raw")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Track ingestion statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "endpoints_processed": set(),
            "start_time": None,
            "end_time": None,
        }

    async def run(self) -> Dict[str, Any]:
        """Run full ingestion cycle for all endpoints and tickers.

        Returns:
            Dictionary with run statistics and saved file locations
        """
        self.stats["start_time"] = datetime.utcnow()
        logger.info(f"Starting REST ingestion run at {self.stats['start_time']}")

        # Get configured symbols
        symbols = self.settings.symbols
        logger.info(f"Target symbols: {symbols}")

        # Results storage
        results = {
            "stats": self.stats,
            "saved_files": [],
            "errors": [],
        }

        async with UnusualWhalesClient() as client:
            # First, fetch all global endpoints (no ticker required)
            logger.info(f"Fetching {len(GLOBAL_ENDPOINTS)} global endpoints...")
            for endpoint in GLOBAL_ENDPOINTS:
                result = await self._fetch_and_save(client, endpoint, ticker=None)
                self._update_stats(result)
                if result["success"]:
                    results["saved_files"].append(result.get("file_path"))
                else:
                    results["errors"].append(result)

            # Then fetch ticker-specific endpoints
            logger.info(f"Fetching {len(TICKER_ENDPOINTS)} endpoints for {len(symbols)} symbols...")
            for symbol in symbols:
                logger.info(f"Processing symbol: {symbol}")
                for endpoint in TICKER_ENDPOINTS:
                    result = await self._fetch_and_save(client, endpoint, ticker=symbol)
                    self._update_stats(result)
                    if result["success"]:
                        results["saved_files"].append(result.get("file_path"))
                    else:
                        results["errors"].append(result)

        self.stats["end_time"] = datetime.utcnow()
        duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()

        # Log summary
        logger.info(
            f"Ingestion completed in {duration:.2f}s. "
            f"Success: {self.stats['successful_requests']}, "
            f"Failed: {self.stats['failed_requests']}, "
            f"Total: {self.stats['total_requests']}"
        )

        return results

    async def _fetch_and_save(
        self,
        client: UnusualWhalesClient,
        endpoint,
        ticker: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch endpoint data and save to disk.

        Args:
            client: HTTP client instance
            endpoint: Endpoint definition
            ticker: Optional ticker symbol

        Returns:
            Dictionary with fetch results and file path
        """
        # Prepare identifiers for logging
        identifier = f"{endpoint.key}" + (f":{ticker}" if ticker else "")
        logger.debug(f"Fetching {identifier}")

        try:
            # Fetch from API
            response = await client.fetch_endpoint(endpoint, ticker=ticker)

            if response["success"]:
                # Save to disk
                file_path = self._save_response(
                    endpoint_key=endpoint.key,
                    ticker=ticker,
                    data=response["data"],
                    metadata={
                        "status_code": response["status_code"],
                        "timestamp": response["timestamp"],
                        "endpoint": endpoint.key,
                        "ticker": ticker,
                    }
                )

                logger.info(f"✓ {identifier} → {file_path}")
                return {
                    "success": True,
                    "endpoint": endpoint.key,
                    "ticker": ticker,
                    "file_path": str(file_path),
                }
            else:
                logger.error(
                    f"✗ {identifier}: {response.get('error', 'Unknown error')} "
                    f"(status: {response.get('status_code', 'N/A')})"
                )
                return {
                    "success": False,
                    "endpoint": endpoint.key,
                    "ticker": ticker,
                    "error": response.get("error"),
                    "status_code": response.get("status_code"),
                }

        except Exception as e:
            logger.error(f"✗ {identifier}: Unexpected error: {e}", exc_info=True)
            return {
                "success": False,
                "endpoint": endpoint.key,
                "ticker": ticker,
                "error": str(e),
            }

    def _save_response(
        self,
        endpoint_key: str,
        ticker: Optional[str],
        data: Any,
        metadata: Dict[str, Any]
    ) -> Path:
        """Save API response to disk with metadata.

        Args:
            endpoint_key: Endpoint identifier
            ticker: Optional ticker symbol
            data: Response data to save
            metadata: Additional metadata about the request

        Returns:
            Path to the saved file
        """
        # Create endpoint-specific directory
        endpoint_dir = self.data_dir / endpoint_key
        endpoint_dir.mkdir(exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.utcnow().isoformat().replace(":", "-").replace(".", "-")
        if ticker:
            filename = f"{ticker}_{timestamp}.json"
        else:
            filename = f"{timestamp}.json"

        file_path = endpoint_dir / filename

        # Prepare data to save (include metadata)
        save_data = {
            "metadata": {
                **metadata,
                "saved_at": datetime.utcnow().isoformat(),
                "endpoint_key": endpoint_key,
            },
            "data": data,
        }

        # Write to file
        with open(file_path, "w") as f:
            json.dump(save_data, f, indent=2, default=str)

        # Also update index file for this endpoint
        self._update_index(endpoint_key, ticker, file_path, metadata)

        return file_path

    def _update_index(
        self,
        endpoint_key: str,
        ticker: Optional[str],
        file_path: Path,
        metadata: Dict[str, Any]
    ):
        """Update the index file for an endpoint with fetch metadata.

        Args:
            endpoint_key: Endpoint identifier
            ticker: Optional ticker symbol
            file_path: Path to the saved data file
            metadata: Request metadata
        """
        # Create index file path (NDJSON format for easy appending)
        index_path = self.data_dir / endpoint_key / "index.ndjson"

        # Prepare index entry
        index_entry = {
            "file": file_path.name,
            "ticker": ticker,
            "fetched_at": datetime.utcnow().isoformat(),
            "status_code": metadata.get("status_code"),
            "timestamp": metadata.get("timestamp"),
        }

        # Append to index file
        with open(index_path, "a") as f:
            f.write(json.dumps(index_entry) + "\n")

    def _update_stats(self, result: Dict[str, Any]):
        """Update ingestion statistics based on result.

        Args:
            result: Fetch result dictionary
        """
        self.stats["total_requests"] += 1

        if result["success"]:
            self.stats["successful_requests"] += 1
        else:
            self.stats["failed_requests"] += 1

        # Track unique endpoints processed
        endpoint_key = result["endpoint"]
        if result.get("ticker"):
            endpoint_key = f"{endpoint_key}:{result['ticker']}"
        self.stats["endpoints_processed"].add(endpoint_key)


async def run_ingestion(data_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Convenience function to run ingestion.

    Args:
        data_dir: Optional data directory path

    Returns:
        Ingestion results dictionary
    """
    runner = RestIngestionRunner(data_dir)
    return await runner.run()