"""Definitions of REST ingestion jobs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable

from ..config import IngestionSettings
from ..persistence.postgres import PostgresRepository


@dataclass
class RestRequestSpec:
    """Represents a single REST request to execute."""

    name: str
    path: str
    params: dict[str, Any] | None
    tokens: int
    context: dict[str, Any]
    scope: str | None
    endpoint_key: str


ResponseProcessor = Callable[[Any, RestRequestSpec, PostgresRepository], "Awaitable[None]"]


@dataclass
class RestJobDefinition:
    """Metadata for a scheduled REST job."""

    name: str
    cadence_seconds: int
    request_builder: Callable[[IngestionSettings], Iterable[RestRequestSpec]]
    processor: ResponseProcessor


def _ticker_request_builder(
    endpoint_key: str,
    path_template: str,
    params: dict[str, Any] | None = None,
    name_suffix: str | None = None,
) -> Callable[[IngestionSettings], Iterable[RestRequestSpec]]:
    """Create a builder that issues one request per configured ticker."""

    def _builder(settings: IngestionSettings) -> Iterable[RestRequestSpec]:
        for ticker in settings.target_tickers:
            scope = f"ticker:{ticker}"
            formatted_path = path_template.format(ticker=ticker)
            yield RestRequestSpec(
                name=f"{endpoint_key}:{ticker}" if name_suffix is None else f"{endpoint_key}:{ticker}:{name_suffix}",
                path=formatted_path,
                params=dict(params) if params else None,
                tokens=1,
                context={"ticker": ticker},
                scope=scope,
                endpoint_key=endpoint_key,
            )

    return _builder


def _static_request_builder(
    endpoint_key: str,
    path: str,
    params: dict[str, Any] | None = None,
    scope: str | None = None,
) -> Callable[[IngestionSettings], Iterable[RestRequestSpec]]:
    """Create a builder that issues a single static request."""

    def _builder(_: IngestionSettings) -> Iterable[RestRequestSpec]:
        yield RestRequestSpec(
            name=endpoint_key,
            path=path,
            params=dict(params) if params else None,
            tokens=1,
            context={},
            scope=scope,
            endpoint_key=endpoint_key,
        )

    return _builder


async def default_rest_processor(data: Any, request: RestRequestSpec, repository: PostgresRepository) -> None:
    """Store the raw JSON payload for a REST endpoint."""

    await repository.store_rest_payload(
        endpoint=request.endpoint_key,
        scope=request.scope,
        payload=data,
        context=request.context,
    )


def build_job_catalog(settings: IngestionSettings) -> list[RestJobDefinition]:
    """Assemble REST job catalogue based on configuration."""

    cadences = settings.rest_job_cadences

    ticker_jobs: list[tuple[str, str, dict[str, Any] | None]] = [
        ("stock_darkpool", "/api/darkpool/{ticker}", None),
        ("etf_exposure", "/api/etfs/{ticker}/exposure", None),
        ("etf_in_outflow", "/api/etfs/{ticker}/in-outflow", None),
        ("market_etf_tide", "/api/market/{ticker}/etf-tide", None),
        ("stock_flow_alerts", "/api/stock/{ticker}/flow-alerts", {"limit": 100}),
        ("stock_flow_per_expiry", "/api/stock/{ticker}/flow-per-expiry", None),
        ("stock_greek_exposure", "/api/stock/{ticker}/greek-exposure", None),
        ("stock_greek_exposure_expiry", "/api/stock/{ticker}/greek-exposure/expiry", None),
        ("stock_greek_exposure_strike", "/api/stock/{ticker}/greek-exposure/strike", None),
        ("stock_greek_flow", "/api/stock/{ticker}/greek-flow", None),
        ("stock_interpolated_iv", "/api/stock/{ticker}/interpolated-iv", None),
        ("stock_iv_rank", "/api/stock/{ticker}/iv-rank", None),
        ("stock_max_pain", "/api/stock/{ticker}/max-pain", None),
        ("stock_net_prem_ticks", "/api/stock/{ticker}/net-prem-ticks", None),
        ("stock_nope", "/api/stock/{ticker}/nope", None),
        ("stock_ohlc_1m", "/api/stock/{ticker}/ohlc/1m", {"limit": 500}),
        ("stock_oi_change", "/api/stock/{ticker}/oi-change", None),
        ("stock_option_chains", "/api/stock/{ticker}/option-chains", None),
        ("stock_option_stock_price_levels", "/api/stock/{ticker}/option/stock-price-levels", None),
        ("stock_options_volume", "/api/stock/{ticker}/options-volume", None),
        ("stock_spot_exposures", "/api/stock/{ticker}/spot-exposures", None),
        ("stock_spot_exposures_strike", "/api/stock/{ticker}/spot-exposures/strike", None),
        ("stock_stock_state", "/api/stock/{ticker}/stock-state", None),
        ("stock_stock_volume_price_levels", "/api/stock/{ticker}/stock-volume-price-levels", None),
        ("stock_volatility_realized", "/api/stock/{ticker}/volatility/realized", None),
        ("stock_volatility_stats", "/api/stock/{ticker}/volatility/stats", None),
        ("stock_volatility_term_structure", "/api/stock/{ticker}/volatility/term-structure", None),
    ]

    catalog: list[RestJobDefinition] = []

    for key, path_template, params in ticker_jobs:
        cadence = cadences.get(key)
        if cadence is None:
            continue
        catalog.append(
            RestJobDefinition(
                name=key,
                cadence_seconds=cadence,
                request_builder=_ticker_request_builder(key, path_template, params=params),
                processor=default_rest_processor,
            )
        )

    static_jobs: list[tuple[str, str, dict[str, Any] | None, str | None]] = [
        ("market_economic_calendar", "/api/market/economic-calendar", None, "market"),
        ("market_market_tide", "/api/market/market-tide", None, "market"),
        ("market_oi_change", "/api/market/oi-change", None, "market"),
        ("market_top_net_impact", "/api/market/top-net-impact", None, "market"),
        ("market_total_options_volume", "/api/market/total-options-volume", {"limit": 100}, "market"),
        ("net_flow_expiry", "/api/net-flow/expiry", None, "market"),
    ]

    for key, path, params, scope in static_jobs:
        cadence = cadences.get(key)
        if cadence is None:
            continue
        catalog.append(
            RestJobDefinition(
                name=key,
                cadence_seconds=cadence,
                request_builder=_static_request_builder(key, path, params=params, scope=scope),
                processor=default_rest_processor,
            )
        )

    return catalog
