from datetime import datetime, timezone

import pytest

from json import load
from pathlib import Path

from ingestion.serializers import FlowAlertMessage, OptionTradeMessage, PriceTickMessage

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "uw" / "ws"


def test_flow_alert_from_raw() -> None:
    with (DATA_DIR / "flow_alerts.json").open() as handle:
        _, payload = load(handle)

    message = FlowAlertMessage.from_raw(payload)

    assert message.alert_id == payload["id"]
    assert message.ticker == payload["ticker"]
    assert message.event_timestamp.tzinfo is not None
    assert message.trade_ids == [str(tid) for tid in payload["trade_ids"]]
    assert message.raw_payload == payload
    stream_payload = message.redis_stream_payload()
    assert stream_payload["alert_id"] == payload["id"]


def test_price_tick_from_raw() -> None:
    with (DATA_DIR / "price_tick.json").open() as handle:
        _, payload = load(handle)
    payload.setdefault("ticker", "SPY")

    message = PriceTickMessage.from_raw(payload)

    assert message.ticker
    assert message.last_price == pytest.approx(float(payload["close"]))
    assert message.event_timestamp.tzinfo is not None
    assert message.raw_payload == payload
    stream_payload = message.redis_stream_payload()
    assert stream_payload["last_price"] == f"{float(payload['close']):.4f}"


def test_option_trade_from_raw() -> None:
    with (DATA_DIR / "option_trade.json").open() as handle:
        payload = load(handle)

    message = OptionTradeMessage.from_raw(payload)

    assert message.trade_id == payload["id"]
    assert message.option_symbol == payload["option_symbol"]
    assert message.event_timestamp.tzinfo is not None
    assert message.ticker == payload["underlying_symbol"]
    stream_payload = message.redis_stream_payload()
    assert stream_payload["trade_id"] == payload["id"]
