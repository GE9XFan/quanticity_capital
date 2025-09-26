from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ingestion.alpha_vantage.macro_cpi import _validate_payload as validate_cpi
from src.ingestion.alpha_vantage.macro_inflation import _validate_payload as validate_inflation
from src.ingestion.alpha_vantage.macro_real_gdp import _validate_payload as validate_real_gdp
from src.ingestion.alpha_vantage.treasury_yield import _validate_payload as validate_treasury_yield
from src.ingestion.alpha_vantage.federal_funds_rate import (
    _validate_payload as validate_federal_funds_rate,
)
from src.ingestion.alpha_vantage._shared import PayloadValidationError


def _load_sample(name: str) -> dict:
    sample_path = Path(f"docs/samples/alpha_vantage/macro/{name}.json")
    with sample_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_real_gdp_validator_accepts_sample() -> None:
    payload = _load_sample("real_gdp")
    assert validate_real_gdp(payload, "US") == payload


def test_real_gdp_validator_rejects_missing_data() -> None:
    payload = {"name": "Real GDP", "data": []}
    with pytest.raises(PayloadValidationError):
        validate_real_gdp(payload, "US")


def test_cpi_validator_accepts_sample() -> None:
    payload = _load_sample("cpi")
    assert validate_cpi(payload, "US") == payload


def test_cpi_validator_rejects_missing_fields() -> None:
    payload = {"name": "Consumer Price Index", "data": [{"value": "1.00"}]}
    with pytest.raises(PayloadValidationError):
        validate_cpi(payload, "US")


def test_inflation_validator_accepts_sample() -> None:
    payload = _load_sample("inflation")
    assert validate_inflation(payload, "US") == payload


def test_inflation_validator_rejects_bad_content() -> None:
    payload = {"name": "Inflation", "data": "bad"}
    with pytest.raises(PayloadValidationError):
        validate_inflation(payload, "US")


def test_treasury_yield_validator_accepts_sample() -> None:
    payload = _load_sample("treasury_yield_10year")
    assert validate_treasury_yield(payload, "US10Y") == payload


def test_treasury_yield_validator_rejects_missing_fields() -> None:
    payload = {"name": "Treasury Yield", "data": [{"date": "2025-09-19"}]}
    with pytest.raises(PayloadValidationError):
        validate_treasury_yield(payload, "US10Y")


def test_federal_funds_rate_validator_accepts_sample() -> None:
    payload = _load_sample("federal_funds_rate")
    assert validate_federal_funds_rate(payload, "US") == payload


def test_federal_funds_rate_validator_rejects_bad_series() -> None:
    payload = {"name": "Federal Funds Rate", "data": "oops"}
    with pytest.raises(PayloadValidationError):
        validate_federal_funds_rate(payload, "US")
