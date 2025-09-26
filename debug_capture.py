#!/usr/bin/env python3
"""Debug script to capture raw Alpha Vantage API responses."""

import asyncio
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
if not API_KEY:
    raise ValueError("ALPHA_VANTAGE_API_KEY not set in environment")

API_URL = "https://www.alphavantage.co/query"


async def fetch_endpoint(function: str, symbol: str | None = None, **params) -> dict:
    """Fetch raw response from Alpha Vantage API."""
    query_params = {
        "function": function,
        "apikey": API_KEY,
        **params
    }

    if symbol:
        query_params["symbol"] = symbol

    async with httpx.AsyncClient() as client:
        response = await client.get(API_URL, params=query_params)
        response.raise_for_status()

        # Handle CSV responses
        if "datatype" in params and params["datatype"] == "json":
            # This is a special case for EARNINGS_CALENDAR which returns CSV by default
            content = response.text
            # Parse as CSV and convert to dict structure
            import csv
            import io
            reader = csv.DictReader(io.StringIO(content))
            data = list(reader)
            return {"earningsCalendar": data}

        return response.json()


async def main():
    """Capture raw responses for failing endpoints."""

    # EARNINGS_ESTIMATES
    print("Fetching EARNINGS_ESTIMATES for NVDA...")
    earnings_est = await fetch_endpoint("EARNINGS_ESTIMATES", "NVDA")
    with open("debug_earnings_estimates_NVDA.json", "w") as f:
        json.dump(earnings_est, f, indent=2)
    print(f"  Keys: {list(earnings_est.keys())}")

    # SHARES_OUTSTANDING
    print("Fetching SHARES_OUTSTANDING for NVDA...")
    shares = await fetch_endpoint("SHARES_OUTSTANDING", "NVDA")
    with open("debug_shares_outstanding_NVDA.json", "w") as f:
        json.dump(shares, f, indent=2)
    print(f"  Keys: {list(shares.keys())}")

    # EARNINGS_CALL_TRANSCRIPT
    print("Fetching EARNINGS_CALL_TRANSCRIPT for NVDA Q3 2024...")
    transcript = await fetch_endpoint("EARNINGS_CALL_TRANSCRIPT", "NVDA", quarter="2024Q3")
    with open("debug_earnings_call_transcript_NVDA_2024Q3.json", "w") as f:
        json.dump(transcript, f, indent=2)
    print(f"  Keys: {list(transcript.keys())}")

    print("\nDebug files created. Check the JSON files for actual structure.")


if __name__ == "__main__":
    asyncio.run(main())