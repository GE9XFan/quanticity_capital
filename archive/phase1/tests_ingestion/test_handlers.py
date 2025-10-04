import asyncio
from json import load
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from ingestion.aggregators.price_bars import PriceBarAggregator
from ingestion.handlers import FlowAlertHandler, PriceHandler
from ingestion.serializers import FlowAlertMessage, PriceTickMessage

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "uw" / "ws"


def test_flow_alert_handler_invokes_dependencies() -> None:
    publisher = SimpleNamespace(publish_flow_alert=AsyncMock())
    repository = SimpleNamespace(insert_flow_alert=AsyncMock())
    handler = FlowAlertHandler(publisher=publisher, repository=repository)

    with (DATA_DIR / "flow_alerts.json").open() as handle:
        channel, payload = load(handle)
    assert channel == "flow-alerts"

    asyncio.run(handler.handle(payload))

    repository.insert_flow_alert.assert_awaited_once()
    publisher.publish_flow_alert.assert_awaited_once()


def test_price_handler_filters_tickers() -> None:
    publisher = SimpleNamespace(publish_price_tick=AsyncMock(), publish_price_bar=AsyncMock())
    repository = SimpleNamespace(upsert_price_tick=AsyncMock())
    aggregator = PriceBarAggregator()
    handler = PriceHandler(
        publisher=publisher,
        repository=repository,
        tickers=["SPY", "QQQ"],
        aggregator=aggregator,
    )

    with (DATA_DIR / "price_tick.json").open() as handle:
        channel, valid_payload = load(handle)
    assert channel.startswith("price:")

    asyncio.run(handler.handle(valid_payload))
    repository.upsert_price_tick.assert_awaited_once()
    publisher.publish_price_tick.assert_awaited_once()
    assert publisher.publish_price_bar.await_count >= 1

    invalid_payload = {
        "ticker": "MSFT",
        "timestamp": "2024-01-03T13:00:02Z",
        "price": 360.12,
    }

    asyncio.run(handler.handle(invalid_payload))
    repository.upsert_price_tick.assert_awaited_once()  # unchanged
    publisher.publish_price_tick.assert_awaited_once()
