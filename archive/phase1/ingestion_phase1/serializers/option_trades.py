"""Serializers for option trade flow payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import AliasChoices, BaseModel, Field
from pydantic.config import ConfigDict


class OptionTradeMessage(BaseModel):
    """Structure option trade ticks for persistence."""

    trade_id: str = Field(validation_alias=AliasChoices("trade_id", "id"))
    ticker: str = Field(validation_alias=AliasChoices("ticker", "underlying", "underlying_symbol"))
    option_symbol: str = Field(validation_alias=AliasChoices("option_symbol", "symbol"))
    event_timestamp: datetime = Field(validation_alias=AliasChoices("timestamp", "event_timestamp", "executed_at"))
    price: float | None = Field(default=None)
    size: int | None = Field(default=None)
    premium: float | None = Field(default=None)
    side: str | None = Field(default=None)
    exchange: str | None = Field(default=None)
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    @classmethod
    def from_raw(cls, payload: dict[str, Any]) -> "OptionTradeMessage":
        """Parse raw payload retaining the original."""

        mutable_payload = dict(payload)
        if "trade_id" in mutable_payload:
            mutable_payload["trade_id"] = str(mutable_payload["trade_id"])
        if "id" in mutable_payload and "trade_id" not in mutable_payload:
            mutable_payload["id"] = str(mutable_payload["id"])
        if "ticker" not in mutable_payload:
            ticker = mutable_payload.get("underlying_symbol") or mutable_payload.get("underlying")
            if ticker is not None:
                mutable_payload["ticker"] = ticker
        if "timestamp" not in mutable_payload:
            execution = mutable_payload.get("executed_at")
            if isinstance(execution, (int, float)):
                mutable_payload["timestamp"] = datetime.fromtimestamp(execution / 1000, tz=timezone.utc).isoformat()
            elif isinstance(execution, str) and execution.isdigit():
                mutable_payload["timestamp"] = datetime.fromtimestamp(int(execution) / 1000, tz=timezone.utc).isoformat()
            elif execution is not None:
                mutable_payload["timestamp"] = execution
        model = cls.model_validate(mutable_payload)
        model.raw_payload = dict(payload)
        return model

    def redis_stream_payload(self) -> dict[str, str]:
        """Return stream payload for Redis."""

        payload = {
            "trade_id": self.trade_id,
            "option_symbol": self.option_symbol,
            "event_timestamp": self.event_timestamp.isoformat(),
        }
        if self.price is not None:
            payload["price"] = f"{self.price:.2f}"
        if self.size is not None:
            payload["size"] = str(self.size)
        if self.premium is not None:
            payload["premium"] = f"{self.premium:.2f}"
        if self.side:
            payload["side"] = self.side
        return payload
