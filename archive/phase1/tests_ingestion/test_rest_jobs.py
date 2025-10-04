import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ingestion.config import IngestionSettings
from ingestion.rest.jobs import (
    RestRequestSpec,
    build_job_catalog,
    default_rest_processor,
)


def make_settings() -> IngestionSettings:
    return IngestionSettings(unusual_whales_api_token="test-token")


def test_build_job_catalog_includes_expected_jobs() -> None:
    settings = make_settings()
    catalog = build_job_catalog(settings)
    names = {job.name for job in catalog}
    assert "stock_flow_alerts" in names
    assert "market_economic_calendar" in names
    assert "net_flow_expiry" in names


@pytest.mark.parametrize("job_name", ["stock_nope", "market_economic_calendar"])
def test_default_rest_processor_persists_rows(job_name: str) -> None:
    repository = SimpleNamespace(store_rest_payload=AsyncMock())
    request = RestRequestSpec(
        name=f"{job_name}:SPY",
        path="/fake",
        params={"ticker": "SPY"},
        tokens=1,
        context={"ticker": "SPY"},
        scope="ticker:SPY",
        endpoint_key=job_name,
    )
    payload = {"data": [{"dummy": True}]}

    asyncio.run(default_rest_processor(payload, request, repository))

    repository.store_rest_payload.assert_awaited_once_with(
        endpoint=job_name,
        scope="ticker:SPY",
        payload=payload,
        context={"ticker": "SPY"},
    )
