"""Alpha Vantage ingestion connector backed by the shared runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Protocol, Sequence

import httpx

from quanticity_capital.runner import IngestionJob, RetryPolicy, Runner, RunnerResult

from .rate_limits import (
    ALPHA_VANTAGE_RATE_LIMITER_SPECS,
    RateLimiterSpec,
    build_rate_limiter_map,
)


class AlphaVantageError(RuntimeError):
    """Base exception for Alpha Vantage connector failures."""


class AlphaVantageRetryableError(AlphaVantageError):
    """Errors that should trigger a retry under the shared runner."""


class AlphaVantageThrottleError(AlphaVantageRetryableError):
    """Raised when Alpha Vantage signals throttling via Note/Information messages."""


class AlphaVantageTransportError(AlphaVantageRetryableError):
    """Raised when the HTTP client fails to reach Alpha Vantage."""


class AlphaVantageInvalidResponseError(AlphaVantageError):
    """Raised when the response payload cannot be parsed."""


class AlphaVantageInvalidRequestError(AlphaVantageError):
    """Raised when Alpha Vantage rejects the request as invalid."""


class AlphaVantageClientProtocol(Protocol):
    """Contract for Alpha Vantage clients used by the connector."""

    def fetch(self, params: Mapping[str, Any]) -> Any:  # pragma: no cover - protocol definition
        """Execute a request with the provided query parameters."""


class AlphaVantageHttpClient:
    """Thin httpx-backed client for Alpha Vantage requests."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://www.alphavantage.co/query",
        timeout: float | httpx.Timeout | None = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
        )

    def fetch(self, params: Mapping[str, Any]) -> Any:
        query: Dict[str, Any] = dict(params)
        query.setdefault("apikey", self._api_key)

        try:
            response = self._client.get("", params=query)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network error path
            raise AlphaVantageTransportError(
                f"Alpha Vantage responded with HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:  # pragma: no cover - network error path
            raise AlphaVantageTransportError("Alpha Vantage request failed") from exc

        content_type = response.headers.get("Content-Type", "")
        if "text/csv" in content_type:
            return response.text

        try:
            return response.json()
        except ValueError as exc:  # pragma: no cover - depends on live API behaviour
            raise AlphaVantageInvalidResponseError("Failed to decode Alpha Vantage JSON response") from exc

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AlphaVantageHttpClient":  # pragma: no cover - convenience
        return self

    def __exit__(self, *_: Any) -> None:  # pragma: no cover - convenience
        self.close()


@dataclass(frozen=True)
class AlphaVantageEndpointSpec:
    """Declarative description of an Alpha Vantage endpoint."""

    endpoint: str
    entity: str
    static_params: Mapping[str, Any]
    param_mapping: Mapping[str, str] = field(default_factory=dict)
    context_keys: Sequence[str] = field(default_factory=tuple)
    redis_key_template: str = ""
    rate_limit_key: str = "alpha_vantage:core"
    retry_policy: RetryPolicy | None = None
    ttl_seconds: Optional[int] = None

    def build_params(self, context: Mapping[str, Any]) -> Dict[str, Any]:
        params = dict(self.static_params)
        for key in self.context_keys:
            if key not in context:
                raise ValueError(f"Missing context value '{key}' for endpoint {self.endpoint}")
            param_name = self.param_mapping.get(key, key)
            params[param_name] = context[key]
        return params

    def build_metadata(self, context: Mapping[str, Any]) -> tuple[Optional[str], Dict[str, Any]]:
        context_snapshot = {key: context[key] for key in self.context_keys if key in context}
        redis_key: Optional[str]
        if self.redis_key_template:
            try:
                redis_key = self.redis_key_template.format(**context)
            except KeyError as exc:
                missing = exc.args[0]
                raise ValueError(
                    f"Missing context value '{missing}' for redis key template '{self.redis_key_template}'"
                ) from exc
        else:
            redis_key = None
        return redis_key, context_snapshot


TECHASCOPE_UNIVERSE: tuple[str, ...] = (
    "SPY",
    "QQQ",
    "IWM",
    "NVDA",
    "AAPL",
    "MSFT",
    "GOOGL",
    "META",
    "ORCL",
    "AMZN",
    "TSLA",
    "DIS",
    "V",
    "COST",
    "WMT",
    "GE",
    "AMD",
)

EQUITY_UNIVERSE: tuple[str, ...] = tuple(
    symbol for symbol in TECHASCOPE_UNIVERSE if symbol not in {"SPY", "QQQ", "IWM"}
)


ALPHA_VANTAGE_ENDPOINT_SPECS: Dict[str, AlphaVantageEndpointSpec] = {
    "REALTIME_OPTIONS": AlphaVantageEndpointSpec(
        endpoint="REALTIME_OPTIONS",
        entity="realtime_options",
        static_params={"function": "REALTIME_OPTIONS", "require_greeks": "true"},
        param_mapping={"symbol": "symbol"},
        context_keys=("symbol",),
        redis_key_template="raw:alpha_vantage:realtime_options:{symbol}",
        rate_limit_key="alpha_vantage:core",
        ttl_seconds=60,
    ),
    "TIME_SERIES_INTRADAY": AlphaVantageEndpointSpec(
        endpoint="TIME_SERIES_INTRADAY",
        entity="time_series_intraday",
        static_params={
            "function": "TIME_SERIES_INTRADAY",
            "interval": "1min",
            "outputsize": "full",
            "extended_hours": "true",
        },
        context_keys=("symbol",),
        redis_key_template="raw:alpha_vantage:time_series_intraday:{symbol}",
        rate_limit_key="alpha_vantage:core",
        ttl_seconds=180,
    ),
    "VWAP": AlphaVantageEndpointSpec(
        endpoint="VWAP",
        entity="vwap",
        static_params={"function": "VWAP", "interval": "1min", "series_type": "close"},
        context_keys=("symbol",),
        redis_key_template="raw:alpha_vantage:vwap:{symbol}",
        rate_limit_key="alpha_vantage:core",
        ttl_seconds=300,
    ),
    "MACD": AlphaVantageEndpointSpec(
        endpoint="MACD",
        entity="macd",
        static_params={
            "function": "MACD",
            "interval": "1min",
            "series_type": "close",
            "fastperiod": "12",
            "slowperiod": "26",
            "signalperiod": "9",
        },
        context_keys=("symbol",),
        redis_key_template="raw:alpha_vantage:macd:{symbol}",
        rate_limit_key="alpha_vantage:core",
        ttl_seconds=300,
    ),
    "BBANDS": AlphaVantageEndpointSpec(
        endpoint="BBANDS",
        entity="bbands",
        static_params={
            "function": "BBANDS",
            "interval": "1min",
            "series_type": "close",
            "time_period": "20",
            "nbdevup": "2",
            "nbdevdn": "2",
            "matype": "0",
        },
        context_keys=("symbol",),
        redis_key_template="raw:alpha_vantage:bbands:{symbol}",
        rate_limit_key="alpha_vantage:core",
        ttl_seconds=300,
    ),
    "TOP_GAINERS_LOSERS": AlphaVantageEndpointSpec(
        endpoint="TOP_GAINERS_LOSERS",
        entity="top_gainers_losers",
        static_params={"function": "TOP_GAINERS_LOSERS"},
        param_mapping={"market": "market"},
        context_keys=("market",),
        redis_key_template="raw:alpha_vantage:top_gainers_losers:{market}",
        rate_limit_key="alpha_vantage:core",
        ttl_seconds=600,
    ),
    "NEWS_SENTIMENT": AlphaVantageEndpointSpec(
        endpoint="NEWS_SENTIMENT",
        entity="news_sentiment",
        static_params={"function": "NEWS_SENTIMENT", "limit": "50", "sort": "LATEST"},
        param_mapping={"symbol": "tickers"},
        context_keys=("symbol",),
        redis_key_template="raw:alpha_vantage:news_sentiment:{symbol}",
        rate_limit_key="alpha_vantage:news",
        ttl_seconds=1800,
    ),
    "REAL_GDP": AlphaVantageEndpointSpec(
        endpoint="REAL_GDP",
        entity="macro:real_gdp",
        static_params={"function": "REAL_GDP"},
        param_mapping={"interval": "interval"},
        context_keys=("interval",),
        redis_key_template="raw:alpha_vantage:macro:real_gdp:{interval}",
        rate_limit_key="alpha_vantage:macro",
        ttl_seconds=86400,
    ),
    "CPI": AlphaVantageEndpointSpec(
        endpoint="CPI",
        entity="macro:cpi",
        static_params={"function": "CPI"},
        param_mapping={"interval": "interval"},
        context_keys=("interval",),
        redis_key_template="raw:alpha_vantage:macro:cpi:{interval}",
        rate_limit_key="alpha_vantage:macro",
        ttl_seconds=86400,
    ),
    "INFLATION": AlphaVantageEndpointSpec(
        endpoint="INFLATION",
        entity="macro:inflation",
        static_params={"function": "INFLATION"},
        redis_key_template="raw:alpha_vantage:macro:inflation",
        rate_limit_key="alpha_vantage:macro",
        ttl_seconds=86400,
    ),
    "TREASURY_YIELD": AlphaVantageEndpointSpec(
        endpoint="TREASURY_YIELD",
        entity="macro:treasury_yield",
        static_params={"function": "TREASURY_YIELD"},
        param_mapping={
            "interval": "interval",
            "maturity": "maturity",
        },
        context_keys=("interval", "maturity"),
        redis_key_template="raw:alpha_vantage:macro:treasury_yield:{interval}:{maturity}",
        rate_limit_key="alpha_vantage:macro",
        ttl_seconds=86400,
    ),
    "FEDERAL_FUNDS_RATE": AlphaVantageEndpointSpec(
        endpoint="FEDERAL_FUNDS_RATE",
        entity="macro:federal_funds_rate",
        static_params={"function": "FEDERAL_FUNDS_RATE"},
        param_mapping={"interval": "interval"},
        context_keys=("interval",),
        redis_key_template="raw:alpha_vantage:macro:federal_funds_rate:{interval}",
        rate_limit_key="alpha_vantage:macro",
        ttl_seconds=86400,
    ),
    "EARNINGS_CALENDAR": AlphaVantageEndpointSpec(
        endpoint="EARNINGS_CALENDAR",
        entity="fundamentals:earnings_calendar",
        static_params={
            "function": "EARNINGS_CALENDAR",
            "horizon": "3month",
            "response_format": "csv",
        },
        redis_key_template="raw:alpha_vantage:fundamentals:earnings_calendar",
        rate_limit_key="alpha_vantage:fundamentals",
        ttl_seconds=172800,
    ),
    "EARNINGS_ESTIMATES": AlphaVantageEndpointSpec(
        endpoint="EARNINGS_ESTIMATES",
        entity="fundamentals:earnings_estimates",
        static_params={"function": "EARNINGS_ESTIMATES"},
        context_keys=("symbol",),
        redis_key_template="raw:alpha_vantage:fundamentals:earnings_estimates:{symbol}",
        rate_limit_key="alpha_vantage:fundamentals",
        ttl_seconds=1209600,
    ),
    "INCOME_STATEMENT": AlphaVantageEndpointSpec(
        endpoint="INCOME_STATEMENT",
        entity="fundamentals:income_statement",
        static_params={"function": "INCOME_STATEMENT"},
        context_keys=("symbol",),
        redis_key_template="raw:alpha_vantage:fundamentals:income_statement:{symbol}",
        rate_limit_key="alpha_vantage:fundamentals",
        ttl_seconds=1209600,
    ),
    "BALANCE_SHEET": AlphaVantageEndpointSpec(
        endpoint="BALANCE_SHEET",
        entity="fundamentals:balance_sheet",
        static_params={"function": "BALANCE_SHEET"},
        context_keys=("symbol",),
        redis_key_template="raw:alpha_vantage:fundamentals:balance_sheet:{symbol}",
        rate_limit_key="alpha_vantage:fundamentals",
        ttl_seconds=1209600,
    ),
    "CASH_FLOW": AlphaVantageEndpointSpec(
        endpoint="CASH_FLOW",
        entity="fundamentals:cash_flow",
        static_params={"function": "CASH_FLOW"},
        context_keys=("symbol",),
        redis_key_template="raw:alpha_vantage:fundamentals:cash_flow:{symbol}",
        rate_limit_key="alpha_vantage:fundamentals",
        ttl_seconds=1209600,
    ),
    "SHARES_OUTSTANDING": AlphaVantageEndpointSpec(
        endpoint="SHARES_OUTSTANDING",
        entity="fundamentals:shares_outstanding",
        static_params={"function": "SHARES_OUTSTANDING"},
        context_keys=("symbol",),
        redis_key_template="raw:alpha_vantage:fundamentals:shares_outstanding:{symbol}",
        rate_limit_key="alpha_vantage:fundamentals",
        ttl_seconds=1209600,
    ),
    "EARNINGS_CALL_TRANSCRIPT": AlphaVantageEndpointSpec(
        endpoint="EARNINGS_CALL_TRANSCRIPT",
        entity="fundamentals:earnings_call_transcript",
        static_params={"function": "EARNINGS_CALL_TRANSCRIPT"},
        context_keys=("symbol", "quarter"),
        redis_key_template="raw:alpha_vantage:fundamentals:earnings_call_transcript:{symbol}:{quarter}",
        rate_limit_key="alpha_vantage:fundamentals",
        ttl_seconds=7776000,
    ),
}


DEFAULT_ALPHA_VANTAGE_CONTEXTS: Dict[str, Sequence[Mapping[str, Any]]] = {
    "REALTIME_OPTIONS": tuple({"symbol": symbol} for symbol in TECHASCOPE_UNIVERSE),
    "TIME_SERIES_INTRADAY": tuple({"symbol": symbol} for symbol in TECHASCOPE_UNIVERSE),
    "VWAP": tuple({"symbol": symbol} for symbol in TECHASCOPE_UNIVERSE),
    "MACD": tuple({"symbol": symbol} for symbol in TECHASCOPE_UNIVERSE),
    "BBANDS": tuple({"symbol": symbol} for symbol in TECHASCOPE_UNIVERSE),
    "TOP_GAINERS_LOSERS": (
        {"market": "US"},
        {"market": "TORONTO"},
        {"market": "LONDON"},
    ),
    "NEWS_SENTIMENT": tuple({"symbol": symbol} for symbol in EQUITY_UNIVERSE),
    "REAL_GDP": (
        {"interval": "quarterly"},
        {"interval": "annual"},
    ),
    "CPI": (
        {"interval": "monthly"},
        {"interval": "semiannual"},
    ),
    "INFLATION": ({},),
    "TREASURY_YIELD": (
        {"interval": "daily", "maturity": "2year"},
        {"interval": "weekly", "maturity": "10year"},
        {"interval": "monthly", "maturity": "30year"},
    ),
    "FEDERAL_FUNDS_RATE": (
        {"interval": "daily"},
        {"interval": "weekly"},
        {"interval": "monthly"},
    ),
    "EARNINGS_CALENDAR": ({},),
    "EARNINGS_ESTIMATES": tuple({"symbol": symbol} for symbol in EQUITY_UNIVERSE),
    "INCOME_STATEMENT": tuple({"symbol": symbol} for symbol in EQUITY_UNIVERSE),
    "BALANCE_SHEET": tuple({"symbol": symbol} for symbol in EQUITY_UNIVERSE),
    "CASH_FLOW": tuple({"symbol": symbol} for symbol in EQUITY_UNIVERSE),
    "SHARES_OUTSTANDING": tuple({"symbol": symbol} for symbol in EQUITY_UNIVERSE),
    "EARNINGS_CALL_TRANSCRIPT": tuple(),
}


class AlphaVantageConnector:
    """Builds runner jobs for Alpha Vantage endpoints using shared specs."""

    def __init__(
        self,
        runner: Runner,
        client: AlphaVantageClientProtocol,
        *,
        specs: Mapping[str, AlphaVantageEndpointSpec] | None = None,
        rate_limiter_specs: Mapping[str, RateLimiterSpec] | None = None,
        default_retry_policy: RetryPolicy | None = None,
        clock: Callable[[], float] | None = None,
        timestamp_factory: Callable[[], datetime] | None = None,
        auto_register_rate_limiters: bool = True,
    ) -> None:
        self._runner = runner
        self._client = client
        self._specs: Dict[str, AlphaVantageEndpointSpec] = dict(
            specs or ALPHA_VANTAGE_ENDPOINT_SPECS
        )
        self._rate_limiter_specs: Dict[str, RateLimiterSpec] = dict(
            rate_limiter_specs or ALPHA_VANTAGE_RATE_LIMITER_SPECS
        )
        self._default_retry_policy = default_retry_policy or RetryPolicy(
            retry_exceptions=(AlphaVantageRetryableError,)
        )
        self._clock = clock or getattr(runner, "_clock", None)
        self._timestamp_factory = timestamp_factory or (lambda: datetime.now(timezone.utc))

        if auto_register_rate_limiters:
            self.ensure_rate_limiters()

    def ensure_rate_limiters(self) -> None:
        """Register any missing Alpha Vantage rate limiters with the runner."""

        existing_keys = set()
        try:
            # Reuse the public runner helper when available.
            existing_keys = {
                key
                for key in self._rate_limiter_specs
                if self._runner.has_rate_limiter(key)
            }
        except AttributeError:  # pragma: no cover - future compatibility guard
            existing_keys = set()

        missing_items = (
            (key, spec)
            for key, spec in self._rate_limiter_specs.items()
            if key not in existing_keys
        )

        limiters: list[tuple[str, Any]] = []
        for key, spec in missing_items:
            limiters.append(
                (
                    key,
                    build_rate_limiter_map({key: spec}, clock=self._clock).pop(key),
                )
            )

        if limiters:
            self._runner.register_rate_limiters(limiters)

    def available_endpoints(self) -> Sequence[str]:
        return tuple(self._specs.keys())

    def default_contexts(self, endpoint: str) -> Sequence[Mapping[str, Any]]:
        return DEFAULT_ALPHA_VANTAGE_CONTEXTS.get(endpoint, tuple())

    def spec_for(self, endpoint: str) -> AlphaVantageEndpointSpec:
        try:
            return self._specs[endpoint]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise KeyError(f"Unknown Alpha Vantage endpoint '{endpoint}'") from exc

    def build_job(self, endpoint: str, context: Mapping[str, Any]) -> IngestionJob:
        if endpoint not in self._specs:
            raise KeyError(f"Unknown Alpha Vantage endpoint '{endpoint}'")

        spec = self._specs[endpoint]
        params = spec.build_params(context)
        redis_key, context_snapshot = spec.build_metadata(context)

        metadata: Dict[str, Any] = {
            "endpoint": spec.endpoint,
            "entity": spec.entity,
        }
        if context_snapshot:
            metadata["context"] = dict(context_snapshot)
        if redis_key is not None:
            metadata["redis_key"] = redis_key
        if spec.ttl_seconds is not None:
            metadata["ttl_seconds"] = spec.ttl_seconds

        retry_policy = spec.retry_policy or self._default_retry_policy

        def operation(attempt: int) -> Dict[str, Any]:
            params_for_attempt = dict(params)
            response = self._client.fetch(params_for_attempt)
            self._inspect_response(response)
            return self._build_envelope(
                spec=spec,
                context=context_snapshot,
                redis_key=redis_key,
                params=params_for_attempt,
                response=response,
                attempt=attempt,
            )

        job_name_parts = ["alpha_vantage", spec.entity]
        if context_snapshot:
            context_fragment = ",".join(
                f"{key}={context_snapshot[key]}" for key in sorted(context_snapshot)
            )
            job_name_parts.append(f"[{context_fragment}]")

        return IngestionJob(
            name=".".join(job_name_parts),
            operation=operation,
            rate_limit_key=spec.rate_limit_key,
            retry_policy=retry_policy,
            metadata=metadata,
        )

    def build_jobs(
        self, endpoint: str, contexts: Iterable[Mapping[str, Any]]
    ) -> Sequence[IngestionJob]:
        return [self.build_job(endpoint, context) for context in contexts]

    def build_default_jobs(self, endpoint: str) -> Sequence[IngestionJob]:
        return self.build_jobs(endpoint, self.default_contexts(endpoint))

    def run(self, endpoint: str, context: Mapping[str, Any]) -> RunnerResult:
        job = self.build_job(endpoint, context)
        return self._runner.run(job)

    def run_many(
        self, endpoint: str, contexts: Iterable[Mapping[str, Any]]
    ) -> Sequence[RunnerResult]:
        return [self.run(endpoint, context) for context in contexts]

    def _inspect_response(self, response: Any) -> None:
        if not isinstance(response, Mapping):
            return
        if "Error Message" in response:
            raise AlphaVantageInvalidRequestError(str(response["Error Message"]))
        if "Note" in response:
            raise AlphaVantageThrottleError(str(response["Note"]))
        if "Information" in response:
            raise AlphaVantageThrottleError(str(response["Information"]))

    def _build_envelope(
        self,
        *,
        spec: AlphaVantageEndpointSpec,
        context: Mapping[str, Any],
        redis_key: Optional[str],
        params: Mapping[str, Any],
        response: Any,
        attempt: int,
    ) -> Dict[str, Any]:
        timestamp = self._timestamp_factory().isoformat().replace("+00:00", "Z")
        envelope: Dict[str, Any] = {
            "source": "alpha_vantage",
            "endpoint": spec.endpoint,
            "entity": spec.entity,
            "context": dict(context),
            "requested_at": timestamp,
            "ttl_applied": spec.ttl_seconds,
            "request_params": dict(params),
            "attempt": attempt,
            "data": response,
        }
        if redis_key is not None:
            envelope["redis_key"] = redis_key
        return envelope


__all__ = [
    "ALPHA_VANTAGE_ENDPOINT_SPECS",
    "DEFAULT_ALPHA_VANTAGE_CONTEXTS",
    "TECHASCOPE_UNIVERSE",
    "AlphaVantageClientProtocol",
    "AlphaVantageConnector",
    "AlphaVantageEndpointSpec",
    "AlphaVantageError",
    "AlphaVantageHttpClient",
    "AlphaVantageInvalidRequestError",
    "AlphaVantageInvalidResponseError",
    "AlphaVantageRetryableError",
    "AlphaVantageThrottleError",
    "AlphaVantageTransportError",
]
