"""Utility to aggregate 1-minute bars from price ticks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict

from ..serializers.price import PriceTickMessage


@dataclass
class PriceBar:
    ticker: str
    start: datetime
    end: datetime
    open: float
    high: float
    low: float
    close: float


class PriceBarAggregator:
    """Aggregate rolling OHLC bars from tick updates."""

    def __init__(self) -> None:
        self._state: Dict[str, PriceBar] = {}

    def add_tick(self, message: PriceTickMessage) -> tuple[PriceBar | None, PriceBar | None]:
        """Update state with a new tick.

        Returns a tuple of (completed_bar, current_bar) where completed_bar is emitted
        when the minute boundary advances.
        """

        rounded_start = message.event_timestamp.replace(second=0, microsecond=0)
        rounded_end = rounded_start.replace(minute=rounded_start.minute + 1)
        ticker = message.ticker.upper()

        current = self._state.get(ticker)
        if current is None or current.start != rounded_start:
            completed = current
            current = PriceBar(
                ticker=ticker,
                start=rounded_start,
                end=rounded_end,
                open=message.last_price,
                high=message.last_price,
                low=message.last_price,
                close=message.last_price,
            )
            self._state[ticker] = current
            return completed, current

        current.high = max(current.high, message.last_price)
        current.low = min(current.low, message.last_price)
        current.close = message.last_price
        return None, current
