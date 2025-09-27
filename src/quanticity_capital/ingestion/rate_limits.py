"""Vendor rate limiter configuration for ingestion connectors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Mapping

from quanticity_capital.runner import RateLimiter


@dataclass(frozen=True)
class RateLimiterSpec:
    """Defines how a rate limiter should be constructed."""

    max_calls: int
    period: float


ALPHA_VANTAGE_RATE_LIMITER_SPECS: Dict[str, RateLimiterSpec] = {
    "alpha_vantage:core": RateLimiterSpec(max_calls=600, period=60.0),
    "alpha_vantage:news": RateLimiterSpec(max_calls=120, period=60.0),
    "alpha_vantage:macro": RateLimiterSpec(max_calls=60, period=60.0),
    "alpha_vantage:fundamentals": RateLimiterSpec(max_calls=60, period=60.0),
}


def build_rate_limiter_map(
    specs: Mapping[str, RateLimiterSpec],
    *,
    clock: Callable[[], float] | None = None,
) -> Dict[str, RateLimiter]:
    """Instantiate concrete rate limiters for the provided specs."""

    return {
        key: RateLimiter(spec.max_calls, spec.period, clock=clock)
        for key, spec in specs.items()
    }


__all__ = [
    "ALPHA_VANTAGE_RATE_LIMITER_SPECS",
    "RateLimiterSpec",
    "build_rate_limiter_map",
]
