from __future__ import annotations

from datetime import datetime, timezone

from src.ingestion.ibkr import quotes


def test_resolve_symbols_filters_unknown() -> None:
    configured = ["NVDA", "AAPL", "MSFT"]
    selected = quotes._resolve_symbols(["NVDA", "SPY"], configured)  # type: ignore[attr-defined]
    assert selected == ["NVDA"]


def test_serialize_ticker_formats_payload() -> None:
    class StubContract:
        exchange = "SMART"
        currency = "USD"

    class StubTicker:
        bid = 101.25
        ask = 101.5
        bidSize = 10
        askSize = 12
        last = 101.4
        lastSize = 5
        close = 100.0
        volume = 12345
        marketPrice = 101.35
        marketDataType = 1
        contract = StubContract()
        time = datetime(2025, 9, 26, 15, 30, tzinfo=timezone.utc)

    timestamp = datetime(2025, 9, 26, 15, 30, tzinfo=timezone.utc)
    payload = quotes._serialize_ticker("NVDA", StubTicker(), timestamp)  # type: ignore[attr-defined]

    assert payload["symbol"] == "NVDA"
    assert payload["quote"]["bid"] == 101.25
    assert payload["quote"]["ask_size"] == 12
    assert payload["timestamp"] == StubTicker.time.isoformat()
    assert payload["contract"]["exchange"] == "SMART"
