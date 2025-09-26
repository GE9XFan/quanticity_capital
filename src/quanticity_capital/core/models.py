"""Shared domain models used across Quanticity modules."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator


class OptionGreeks(BaseModel):
    """Normalized set of option Greeks."""

    delta: float
    gamma: float
    theta: float
    vega: float
    rho: Optional[float] = None

    model_config = {
        "extra": "forbid",
    }

    @field_validator("delta", "gamma", "theta", "vega", "rho", mode="before")
    @classmethod
    def round_small_values(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        return float(value)


class OptionContract(BaseModel):
    """Single option contract with pricing and Greeks."""

    symbol: str
    option_type: Literal["call", "put"]
    strike: float = Field(gt=0)
    expiry: date
    bid: float = Field(ge=0)
    ask: float = Field(ge=0)
    last: Optional[float] = Field(default=None, ge=0)
    volume: int = Field(default=0, ge=0)
    open_interest: int = Field(default=0, ge=0)
    implied_volatility: Optional[float] = Field(default=None, ge=0)
    greeks: OptionGreeks

    model_config = {
        "extra": "forbid",
    }

    @model_validator(mode="after")
    def validate_prices(self) -> "OptionContract":
        if self.bid > self.ask:
            raise ValueError("bid cannot exceed ask")
        if self.last is not None and self.last < 0:
            raise ValueError("last price cannot be negative")
        return self

    @computed_field(return_type=float)
    def mid(self) -> float:
        """Midpoint price rounded to four decimals."""

        return round((self.bid + self.ask) / 2, 4)


class OptionsChain(BaseModel):
    """Collection of option contracts for a symbol and expiry."""

    symbol: str
    as_of: datetime
    expiry: date
    underlying_price: float = Field(gt=0)
    contracts: List[OptionContract]
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "extra": "forbid",
    }

    @field_validator("contracts")
    @classmethod
    def require_contracts(cls, value: List[OptionContract]) -> List[OptionContract]:
        if not value:
            raise ValueError("options chain must include at least one contract")
        return value

    def by_type(self, option_type: Literal["call", "put"]) -> List[OptionContract]:
        """Return all contracts of the requested option type."""

        return [contract for contract in self.contracts if contract.option_type == option_type]


class DealerExposure(BaseModel):
    """Dealer positioning metrics consumed by the signal engine."""

    gamma: float
    vanna: Optional[float] = None
    charm: Optional[float] = None
    delta: Optional[float] = None

    model_config = {
        "extra": "forbid",
    }


class VolatilityRegime(BaseModel):
    """Volatility regime classification."""

    regime: Literal["low", "normal", "high", "extreme"]
    score: float = Field(ge=0, le=1)

    model_config = {
        "extra": "forbid",
    }


class AnalyticsBundle(BaseModel):
    """Snapshot of analytics metrics shared across modules."""

    symbol: str
    as_of: datetime
    dealer_exposure: DealerExposure
    vpin: Optional[float] = Field(default=None, ge=0)
    liquidity_stress_score: Optional[float] = Field(default=None, ge=0, le=1)
    volatility_regime: VolatilityRegime
    metrics: Dict[str, float] = Field(default_factory=dict)
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "extra": "forbid",
    }


class SignalSizing(BaseModel):
    """Sizing details for a proposed signal."""

    units: float
    notional: Optional[float] = None
    max_loss: Optional[float] = None

    model_config = {
        "extra": "forbid",
    }

    @model_validator(mode="after")
    def validate_units(self) -> "SignalSizing":
        if abs(self.units) < 1e-9:
            raise ValueError("position units cannot be zero")
        return self


class SignalPayload(BaseModel):
    """Signal contract shared between evaluation, watchdog, and execution."""

    signal_id: str
    symbol: str
    strategy: str
    direction: Literal["long", "short"]
    generated_at: datetime
    confidence: float = Field(ge=0, le=1)
    sizing: SignalSizing
    analytics: AnalyticsBundle
    rationale: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "extra": "forbid",
    }


class OrderLeg(BaseModel):
    """Single leg of an order request."""

    symbol: str
    quantity: int
    order_type: Literal["market", "limit", "stop", "stop_limit"]
    limit_price: Optional[float] = Field(default=None, gt=0)
    stop_price: Optional[float] = Field(default=None, gt=0)
    tif: Literal["day", "gtc", "fok", "ioc"] = "day"

    model_config = {
        "extra": "forbid",
    }

    @model_validator(mode="after")
    def validate_pricing(self) -> "OrderLeg":
        if self.quantity == 0:
            raise ValueError("order leg quantity cannot be zero")
        if self.order_type in {"limit", "stop_limit"} and self.limit_price is None:
            raise ValueError("limit orders require limit_price")
        if self.order_type in {"stop", "stop_limit"} and self.stop_price is None:
            raise ValueError("stop orders require stop_price")
        return self


class OrderRequest(BaseModel):
    """Execution request generated from an approved signal."""

    order_id: str
    signal_id: str
    submitted_at: datetime
    legs: List[OrderLeg]
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "extra": "forbid",
    }

    @field_validator("legs")
    @classmethod
    def validate_legs(cls, value: List[OrderLeg]) -> List[OrderLeg]:
        if not value:
            raise ValueError("order request requires at least one leg")
        return value


class SocialAttachment(BaseModel):
    """Attachment metadata for social posts."""

    url: str
    title: Optional[str] = None
    mime_type: Optional[str] = None

    model_config = {
        "extra": "forbid",
    }


class SocialPostDraft(BaseModel):
    """Message payload queued for distribution."""

    post_id: str
    platform: Literal["discord", "twitter", "telegram", "reddit"]
    tier: Literal["public", "basic", "premium", "internal"]
    content: str
    created_at: datetime
    scheduled_for: Optional[datetime] = None
    attachments: List[SocialAttachment] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "extra": "forbid",
    }

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content cannot be empty")
        return value


__all__ = [
    "AnalyticsBundle",
    "DealerExposure",
    "OptionContract",
    "OptionGreeks",
    "OptionsChain",
    "OrderLeg",
    "OrderRequest",
    "SignalPayload",
    "SignalSizing",
    "SocialAttachment",
    "SocialPostDraft",
    "VolatilityRegime",
]
