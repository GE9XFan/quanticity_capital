import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from ingestion.handlers.option_trades import OptionTradeHandler


def test_option_trade_handler_flushes_on_buffer() -> None:
    publisher = SimpleNamespace(publish_option_trade=AsyncMock())
    repository = SimpleNamespace(bulk_insert_option_trades=AsyncMock())
    handler = OptionTradeHandler(
        publisher=publisher,
        repository=repository,
        tickers=["SPY"],
        buffer_size=2,
        flush_interval=10.0,
    )

    payload = {
        "trade_id": "1",
        "ticker": "SPY",
        "option_symbol": "SPY250118C00500000",
        "timestamp": "2024-01-03T13:00:00Z",
        "price": 1.25,
    }

    asyncio.run(handler.handle(payload))
    asyncio.run(handler.handle({**payload, "trade_id": "2"}))

    repository.bulk_insert_option_trades.assert_awaited_once()
    assert publisher.publish_option_trade.await_count == 2


def test_option_trade_handler_shutdown_flushes() -> None:
    publisher = SimpleNamespace(publish_option_trade=AsyncMock())
    repository = SimpleNamespace(bulk_insert_option_trades=AsyncMock())
    handler = OptionTradeHandler(
        publisher=publisher,
        repository=repository,
        tickers=["SPY"],
        buffer_size=100,
        flush_interval=100.0,
    )
    payload = {
        "trade_id": "10",
        "ticker": "SPY",
        "option_symbol": "SPY250118C00500000",
        "timestamp": "2024-01-03T13:00:00Z",
    }

    asyncio.run(handler.handle(payload))
    asyncio.run(handler.shutdown())

    repository.bulk_insert_option_trades.assert_awaited_once()
    publisher.publish_option_trade.assert_awaited_once()
