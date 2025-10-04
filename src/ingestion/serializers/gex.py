"""Serializers for Gamma Exposure channels."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, Field
from pydantic.config import ConfigDict


class GexSnapshotMessage(BaseModel):
    ticker: str = Field(validation_alias=AliasChoices("ticker", "symbol"))
    event_timestamp: datetime = Field(validation_alias=AliasChoices("timestamp", "event_timestamp"))
    gamma_exposure: float | None = Field(default=None, validation_alias=AliasChoices("gamma_exposure", "gex"))
    delta_exposure: float | None = Field(default=None, validation_alias=AliasChoices("delta_exposure", "dex"))
    vanna: float | None = None
    charm: float | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    @classmethod
    def from_raw(cls, payload: dict[str, Any]) -> "GexSnapshotMessage":
        model = cls.model_validate(payload)
        model.raw_payload = dict(payload)
        return model


class GexStrikeMessage(BaseModel):
    ticker: str = Field(validation_alias=AliasChoices("ticker", "symbol"))
    strike: float = Field(validation_alias=AliasChoices("strike", "strike_price"))
    event_timestamp: datetime = Field(validation_alias=AliasChoices("timestamp", "event_timestamp"))
    gamma_exposure: float | None = Field(default=None, validation_alias=AliasChoices("gamma_exposure", "gex"))
    open_interest: float | None = Field(default=None, validation_alias=AliasChoices("open_interest", "oi"))
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    @classmethod
    def from_raw(cls, payload: dict[str, Any]) -> "GexStrikeMessage":
        model = cls.model_validate(payload)
        model.raw_payload = dict(payload)
        return model


class GexStrikeExpiryMessage(BaseModel):
    ticker: str = Field(validation_alias=AliasChoices("ticker", "symbol"))
    expiry: datetime = Field(validation_alias=AliasChoices("expiry", "expiration"))
    strike: float = Field(validation_alias=AliasChoices("strike", "strike_price"))
    event_timestamp: datetime = Field(validation_alias=AliasChoices("timestamp", "event_timestamp"))
    gamma_exposure: float | None = Field(default=None)
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    @classmethod
    def from_raw(cls, payload: dict[str, Any]) -> "GexStrikeExpiryMessage":
        model = cls.model_validate(payload)
        model.raw_payload = dict(payload)
        return model
