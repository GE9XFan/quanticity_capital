"""Handshake input schema for IBKR ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence


@dataclass(slots=True)
class RedisStreamContract:
    """Metadata describing a Redis stream or key produced by IBKR."""

    key_pattern: str
    ttl_seconds: int | None
    cadence_hint_seconds: int
    description: str
    symbols: Sequence[str] | None = None


@dataclass(slots=True)
class IBKRHandshakeInputs:
    """Information required before implementing IBKR connectivity."""

    connection_host: str
    connection_port: int
    client_id_pool: List[int]
    use_gateway: bool
    reconnect_backoff_seconds: List[int]
    heartbeat_interval_seconds: int
    pacing_violation_window_seconds: int
    redis_contracts: Dict[str, RedisStreamContract] = field(default_factory=dict)
    level2_rotation_groups: Dict[str, List[str]] = field(default_factory=dict)
    max_concurrent_level2_symbols: int = 3


DEFAULT_CONTRACTS: Dict[str, RedisStreamContract] = {
    "raw:ibkr:l2:{symbol}": RedisStreamContract(
        key_pattern="raw:ibkr:l2:{symbol}",
        ttl_seconds=10,
        cadence_hint_seconds=5,
        description="IBKR level-2 depth snapshot with top 10 levels",
        symbols=(
            "SPY",
            "QQQ",
            "IWM",
            "NVDA",
            "AAPL",
            "MSFT",
            "GOOGL",
            "META",
            "ORCL",
            "AMZN",
            "TSLA",
            "DIS",
            "V",
            "COST",
            "WMT",
            "GE",
            "AMD",
        ),
    ),
    "raw:ibkr:quotes:{symbol}": RedisStreamContract(
        key_pattern="raw:ibkr:quotes:{symbol}",
        ttl_seconds=6,
        cadence_hint_seconds=3,
        description="Top-of-book quote (bid/ask/last/volume)",
        symbols=(
            "SPY",
            "QQQ",
            "IWM",
            "NVDA",
            "AAPL",
            "MSFT",
            "GOOGL",
            "META",
            "ORCL",
            "AMZN",
            "TSLA",
            "DIS",
            "V",
            "COST",
            "WMT",
            "GE",
            "AMD",
        ),
    ),
    "raw:ibkr:account:summary": RedisStreamContract(
        key_pattern="raw:ibkr:account:summary",
        ttl_seconds=30,
        cadence_hint_seconds=15,
        description="Account overview metrics (cash, equity, margin)",
    ),
    "raw:ibkr:account:positions": RedisStreamContract(
        key_pattern="raw:ibkr:account:positions",
        ttl_seconds=30,
        cadence_hint_seconds=15,
        description="Per-position snapshot including quantity and cost basis",
    ),
    "raw:ibkr:account:pnl": RedisStreamContract(
        key_pattern="raw:ibkr:account:pnl",
        ttl_seconds=30,
        cadence_hint_seconds=15,
        description="Account-level realized/unrealized PnL",
    ),
    "raw:ibkr:position:pnl:{symbol}": RedisStreamContract(
        key_pattern="raw:ibkr:position:pnl:{symbol}",
        ttl_seconds=30,
        cadence_hint_seconds=15,
        description="Per-symbol PnL feed",
        symbols=(
            "SPY",
            "QQQ",
            "IWM",
            "NVDA",
            "AAPL",
            "MSFT",
            "GOOGL",
            "META",
            "ORCL",
            "AMZN",
            "TSLA",
            "DIS",
            "V",
            "COST",
            "WMT",
            "GE",
            "AMD",
        ),
    ),
    "stream:ibkr:executions": RedisStreamContract(
        key_pattern="stream:ibkr:executions",
        ttl_seconds=None,
        cadence_hint_seconds=0,
        description="Redis stream capturing fills and order states",
    ),
}


DEFAULT_LEVEL2_GROUPS: Dict[str, List[str]] = {
    "grp1": ["SPY", "QQQ", "IWM"],
    "grp2": ["NVDA", "AAPL", "MSFT"],
    "grp3": ["GOOGL", "META", "ORCL"],
    "grp4": ["AMZN", "TSLA", "DIS"],
    "grp5": ["V", "COST", "WMT"],
    "grp6": ["GE", "AMD"],
}


__all__ = [
    "IBKRHandshakeInputs",
    "RedisStreamContract",
    "DEFAULT_CONTRACTS",
    "DEFAULT_LEVEL2_GROUPS",
]
