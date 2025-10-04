"""Serializer for Unusual Whales news feed."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, Field
from pydantic.config import ConfigDict


class NewsMessage(BaseModel):
    headline_id: str = Field(validation_alias=AliasChoices("headline_id", "id"))
    timestamp: datetime = Field(validation_alias=AliasChoices("timestamp", "published_at"))
    headline: str = Field(validation_alias=AliasChoices("headline", "title"))
    source: str | None = None
    tickers: list[str] | None = None
    is_trump: bool | None = Field(default=None, validation_alias=AliasChoices("is_trump_ts", "is_trump"))
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    @classmethod
    def from_raw(cls, payload: dict[str, Any]) -> "NewsMessage":
        mutable_payload = dict(payload)
        if "headline_id" in mutable_payload:
            mutable_payload["headline_id"] = str(mutable_payload["headline_id"])
        if "id" in mutable_payload and "headline_id" not in mutable_payload:
            mutable_payload["id"] = str(mutable_payload["id"])
        model = cls.model_validate(mutable_payload)
        model.raw_payload = dict(payload)
        if model.tickers is not None:
            model.tickers = [ticker.upper() for ticker in model.tickers]
        return model
