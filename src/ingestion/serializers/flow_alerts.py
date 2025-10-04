"""Serializers for flow alert WebSocket payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import AliasChoices, BaseModel, Field
from pydantic.config import ConfigDict


class FlowAlertMessage(BaseModel):
    """Structured representation of a Unusual Whales flow alert payload."""

    alert_id: str = Field(validation_alias=AliasChoices("alert_id", "id"))
    ticker: str = Field(validation_alias=AliasChoices("ticker", "symbol"))
    event_timestamp: datetime = Field(validation_alias=AliasChoices("timestamp", "event_timestamp"))
    rule_name: str | None = Field(default=None)
    direction: str | None = Field(default=None)
    sweep: bool | None = Field(default=None, validation_alias=AliasChoices("sweep", "is_sweep"))
    premium: float | None = Field(default=None)
    ask_side: bool | None = Field(default=None, validation_alias=AliasChoices("is_ask", "ask_side"))
    bid_side: bool | None = Field(default=None, validation_alias=AliasChoices("is_bid", "bid_side"))
    aggregated_premium: float | None = Field(default=None, validation_alias=AliasChoices("aggregated_premium", "total_premium"))
    trade_ids: list[str] | None = Field(default=None, validation_alias=AliasChoices("trade_ids", "trade_id"))
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    @classmethod
    def from_raw(cls, payload: dict[str, Any]) -> "FlowAlertMessage":
        """Parse a raw payload and retain the original message."""

        mutable_payload = dict(payload)
        # Normalise identifiers to strings for consistency.
        if "alert_id" in mutable_payload:
            mutable_payload["alert_id"] = str(mutable_payload["alert_id"])
        if "id" in mutable_payload and "alert_id" not in mutable_payload:
            mutable_payload["id"] = str(mutable_payload["id"])
        trade_ids_value = mutable_payload.get("trade_ids") or mutable_payload.get("trade_id")
        if isinstance(trade_ids_value, list):
            mutable_payload["trade_ids"] = [str(item) for item in trade_ids_value]
        elif trade_ids_value is not None:
            mutable_payload["trade_ids"] = [str(trade_ids_value)]
        if "timestamp" not in mutable_payload:
            executed_at = mutable_payload.get("executed_at") or mutable_payload.get("start_time")
            if isinstance(executed_at, (int, float)):
                mutable_payload["timestamp"] = datetime.fromtimestamp(executed_at / 1000, tz=timezone.utc).isoformat()
            elif isinstance(executed_at, str) and executed_at.isdigit():
                mutable_payload["timestamp"] = datetime.fromtimestamp(int(executed_at) / 1000, tz=timezone.utc).isoformat()
            elif isinstance(executed_at, str):
                mutable_payload["timestamp"] = executed_at

        model = cls.model_validate(mutable_payload)
        model.raw_payload = dict(payload)
        # Ensure trade IDs are strings for downstream storage.
        if model.trade_ids is not None:
            model.trade_ids = [str(item) for item in model.trade_ids]
        return model

    def redis_stream_payload(self) -> dict[str, str]:
        """Return a Redis stream friendly dictionary."""

        base = {
            "alert_id": self.alert_id,
            "ticker": self.ticker,
            "event_timestamp": self.event_timestamp.isoformat(),
        }
        if self.direction:
            base["direction"] = self.direction
        if self.premium is not None:
            base["premium"] = f"{self.premium:.2f}"
        if self.aggregated_premium is not None:
            base["aggregated_premium"] = f"{self.aggregated_premium:.2f}"
        return base
