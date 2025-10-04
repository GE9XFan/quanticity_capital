"""Serializers for price WebSocket payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import AliasChoices, BaseModel, Field
from pydantic.config import ConfigDict


class PriceTickMessage(BaseModel):
    """Structured representation of a price ticker update from Unusual Whales."""

    ticker: str = Field(validation_alias=AliasChoices("ticker", "symbol", "underlying_symbol"))
    event_timestamp: datetime = Field(validation_alias=AliasChoices("timestamp", "event_timestamp", "time"))
    last_price: float = Field(validation_alias=AliasChoices("price", "last_price", "close"))
    bid: float | None = Field(default=None)
    ask: float | None = Field(default=None)
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    @classmethod
    def from_raw(cls, payload: dict[str, Any]) -> "PriceTickMessage":
        """Parse a raw payload and retain the original message."""

        mutable_payload = dict(payload)
        if "timestamp" not in mutable_payload:
            source_time = mutable_payload.get("time")
            if isinstance(source_time, (int, float)):
                mutable_payload["timestamp"] = datetime.fromtimestamp(source_time / 1000, tz=timezone.utc).isoformat()
            elif isinstance(source_time, str) and source_time.isdigit():
                mutable_payload["timestamp"] = datetime.fromtimestamp(int(source_time) / 1000, tz=timezone.utc).isoformat()
            elif source_time is not None:
                mutable_payload["timestamp"] = source_time
        model = cls.model_validate(mutable_payload)
        model.raw_payload = dict(payload)
        return model

    def redis_stream_payload(self) -> dict[str, str]:
        """Return a Redis stream friendly dictionary."""

        base = {
            "ticker": self.ticker,
            "event_timestamp": self.event_timestamp.isoformat(),
            "last_price": f"{self.last_price:.4f}",
        }
        if self.bid is not None:
            base["bid"] = f"{self.bid:.4f}"
        if self.ask is not None:
            base["ask"] = f"{self.ask:.4f}"
        return base
