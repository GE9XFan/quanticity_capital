"""Unusual Whales REST endpoint definitions.

This module defines all REST endpoints we fetch from Unusual Whales.
Each endpoint is configured with its path template, whether it requires
a ticker parameter, and any query parameters.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class Endpoint:
    """Definition of a single REST endpoint."""

    key: str  # Unique identifier for this endpoint
    path_template: str  # Path template with optional {ticker} placeholder
    requires_ticker: bool  # Whether this endpoint needs a ticker parameter
    query_params: Optional[Dict[str, Any]] = None  # Optional query parameters
    accept_header: str = "application/json"  # Accept header value
    description: str = ""  # Human-readable description


# Define all endpoints we want to fetch
ENDPOINTS = [
    # Dark Pool Data
    Endpoint(
        key="darkpool",
        path_template="/api/darkpool/{ticker}",
        requires_ticker=True,
        accept_header="application/json, text/plain",
        description="Dark pool prints for ticker"
    ),

    # ETF Data
    Endpoint(
        key="etf_exposure",
        path_template="/api/etfs/{ticker}/exposure",
        requires_ticker=True,
        description="ETF exposure data"
    ),
    Endpoint(
        key="etf_inoutflow",
        path_template="/api/etfs/{ticker}/in-outflow",
        requires_ticker=True,
        description="ETF in/outflow data"
    ),

    # Market-Wide Data (no ticker required)
    Endpoint(
        key="economic_calendar",
        path_template="/api/market/economic-calendar",
        requires_ticker=False,
        accept_header="application/json, text/plain",
        description="Economic calendar events"
    ),
    Endpoint(
        key="market_tide",
        path_template="/api/market/market-tide",
        requires_ticker=False,
        accept_header="application/json, text/plain",
        description="Market-wide tide indicators"
    ),
    Endpoint(
        key="market_oi_change",
        path_template="/api/market/oi-change",
        requires_ticker=False,
        description="Market-wide open interest changes"
    ),
    Endpoint(
        key="market_top_net_impact",
        path_template="/api/market/top-net-impact",
        requires_ticker=False,
        accept_header="application/json, text/plain",
        description="Top net impact across market"
    ),
    Endpoint(
        key="market_total_options_volume",
        path_template="/api/market/total-options-volume",
        requires_ticker=False,
        query_params={"limit": 100},
        accept_header="application/json, text/plain",
        description="Total options volume across market"
    ),

    # Net Flow Data
    Endpoint(
        key="net_flow_expiry",
        path_template="/api/net-flow/expiry",
        requires_ticker=False,
        accept_header="application/json, text/plain",
        description="Net flow by expiry"
    ),

    # Ticker-Specific Market Data
    Endpoint(
        key="etf_tide",
        path_template="/api/market/{ticker}/etf-tide",
        requires_ticker=True,
        accept_header="application/json, text/plain",
        description="ETF tide for ticker"
    ),

    # Stock/Options Flow Data
    Endpoint(
        key="flow_alerts",
        path_template="/api/stock/{ticker}/flow-alerts",
        requires_ticker=True,
        query_params={"limit": 100},
        accept_header="application/json, text/plain",
        description="Flow alerts for ticker"
    ),
    Endpoint(
        key="flow_per_expiry",
        path_template="/api/stock/{ticker}/flow-per-expiry",
        requires_ticker=True,
        description="Flow per expiry for ticker"
    ),

    # Greek Exposure Data
    Endpoint(
        key="greek_exposure",
        path_template="/api/stock/{ticker}/greek-exposure",
        requires_ticker=True,
        accept_header="application/json, text/plain",
        description="Greek exposure (spot) for ticker"
    ),
    Endpoint(
        key="greek_exposure_expiry",
        path_template="/api/stock/{ticker}/greek-exposure/expiry",
        requires_ticker=True,
        accept_header="application/json, text/plain",
        description="Greek exposure by expiry"
    ),
    Endpoint(
        key="greek_exposure_strike",
        path_template="/api/stock/{ticker}/greek-exposure/strike",
        requires_ticker=True,
        accept_header="application/json, text/plain",
        description="Greek exposure by strike"
    ),
    Endpoint(
        key="greek_flow",
        path_template="/api/stock/{ticker}/greek-flow",
        requires_ticker=True,
        description="Greek flow for ticker"
    ),

    # Volatility Data
    Endpoint(
        key="interpolated_iv",
        path_template="/api/stock/{ticker}/interpolated-iv",
        requires_ticker=True,
        accept_header="application/json, text/plain",
        description="Interpolated implied volatility"
    ),
    Endpoint(
        key="iv_rank",
        path_template="/api/stock/{ticker}/iv-rank",
        requires_ticker=True,
        accept_header="application/json, text/plain",
        description="IV rank for ticker"
    ),
    Endpoint(
        key="volatility_term_structure",
        path_template="/api/stock/{ticker}/volatility/term-structure",
        requires_ticker=True,
        accept_header="application/json, text/plain",
        description="Volatility term structure"
    ),

    # Options Data
    Endpoint(
        key="max_pain",
        path_template="/api/stock/{ticker}/max-pain",
        requires_ticker=True,
        accept_header="application/json, text/plain",
        description="Max pain levels"
    ),
    Endpoint(
        key="net_prem_ticks",
        path_template="/api/stock/{ticker}/net-prem-ticks",
        requires_ticker=True,
        accept_header="application/json, text/plain",
        description="Net premium ticks"
    ),
    Endpoint(
        key="nope",
        path_template="/api/stock/{ticker}/nope",
        requires_ticker=True,
        description="NOPE indicator"
    ),
    Endpoint(
        key="oi_change",
        path_template="/api/stock/{ticker}/oi-change",
        requires_ticker=True,
        description="Open interest changes for ticker"
    ),
    Endpoint(
        key="option_chains",
        path_template="/api/stock/{ticker}/option-chains",
        requires_ticker=True,
        accept_header="application/json, text/plain",
        description="Option chains data"
    ),
    Endpoint(
        key="option_stock_price_levels",
        path_template="/api/stock/{ticker}/option/stock-price-levels",
        requires_ticker=True,
        accept_header="application/json, text/plain",
        description="Option stock price levels"
    ),
    Endpoint(
        key="options_volume",
        path_template="/api/stock/{ticker}/options-volume",
        requires_ticker=True,
        accept_header="application/json, text/plain",
        description="Options volume for ticker"
    ),

    # Price Data
    Endpoint(
        key="ohlc_1m",
        path_template="/api/stock/{ticker}/ohlc/1m",
        requires_ticker=True,
        query_params={"limit": 500},
        accept_header="application/json, text/plain",
        description="1-minute OHLC bars"
    ),

    # Spot Exposures
    Endpoint(
        key="spot_exposures",
        path_template="/api/stock/{ticker}/spot-exposures",
        requires_ticker=True,
        accept_header="application/json, text/plain",
        description="Spot exposures"
    ),
    Endpoint(
        key="spot_exposures_strike",
        path_template="/api/stock/{ticker}/spot-exposures/strike",
        requires_ticker=True,
        accept_header="application/json, text/plain",
        description="Spot exposures by strike"
    ),

    # Stock State & Volume
    Endpoint(
        key="stock_state",
        path_template="/api/stock/{ticker}/stock-state",
        requires_ticker=True,
        accept_header="application/json, text/plain",
        description="Stock state data"
    ),
    Endpoint(
        key="stock_volume_price_levels",
        path_template="/api/stock/{ticker}/stock-volume-price-levels",
        requires_ticker=True,
        accept_header="application/json, text/plain",
        description="Stock volume price levels"
    ),
]

# Create lookup dictionaries for quick access
ENDPOINTS_BY_KEY = {ep.key: ep for ep in ENDPOINTS}
TICKER_ENDPOINTS = [ep for ep in ENDPOINTS if ep.requires_ticker]
GLOBAL_ENDPOINTS = [ep for ep in ENDPOINTS if not ep.requires_ticker]


def get_endpoint(key: str) -> Optional[Endpoint]:
    """Get endpoint definition by key."""
    return ENDPOINTS_BY_KEY.get(key)


def list_endpoint_keys() -> list[str]:
    """Get list of all endpoint keys."""
    return list(ENDPOINTS_BY_KEY.keys())