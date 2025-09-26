from __future__ import annotations

import json
from pathlib import Path

import asyncio
import pytest

from src.ingestion.alpha_vantage.earnings_call_transcript import (
    _validate_payload as validate_transcript,
)
from src.ingestion.alpha_vantage.earnings_call_transcript import run as run_transcript
from src.ingestion.alpha_vantage.earnings_calendar import (
    _validate_payload as validate_earnings_calendar,
)
from src.ingestion.alpha_vantage.earnings_estimates import (
    _validate_payload as validate_earnings_estimates,
)
from src.ingestion.alpha_vantage.income_statement import (
    _validate_payload as validate_income_statement,
)
from src.ingestion.alpha_vantage.balance_sheet import (
    _validate_payload as validate_balance_sheet,
)
from src.ingestion.alpha_vantage.cash_flow import _validate_payload as validate_cash_flow
from src.ingestion.alpha_vantage.shares_outstanding import (
    _validate_payload as validate_shares_outstanding,
)
from src.ingestion.alpha_vantage._shared import PayloadValidationError


def _load_sample(name: str) -> dict:
    sample_path = Path(f"docs/samples/alpha_vantage/fundamentals/{name}.json")
    with sample_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_earnings_estimates_validator_accepts_sample() -> None:
    payload = _load_sample("earnings_estimates_NVDA")
    assert validate_earnings_estimates(payload, "NVDA") == payload


def test_earnings_estimates_validator_rejects_missing_estimates() -> None:
    payload = {"symbol": "NVDA", "estimates": []}
    with pytest.raises(PayloadValidationError):
        validate_earnings_estimates(payload, "NVDA")


def test_income_statement_validator_accepts_sample() -> None:
    payload = _load_sample("income_statement_NVDA")
    assert validate_income_statement(payload, "NVDA") == payload


def test_income_statement_validator_rejects_missing_reports() -> None:
    payload = {"symbol": "NVDA", "annualReports": []}
    with pytest.raises(PayloadValidationError):
        validate_income_statement(payload, "NVDA")


def test_balance_sheet_validator_accepts_sample() -> None:
    payload = _load_sample("balance_sheet_NVDA")
    assert validate_balance_sheet(payload, "NVDA") == payload


def test_cash_flow_validator_accepts_sample() -> None:
    payload = _load_sample("cash_flow_NVDA")
    assert validate_cash_flow(payload, "NVDA") == payload


def test_shares_outstanding_validator_accepts_sample() -> None:
    payload = _load_sample("shares_outstanding_NVDA")
    assert validate_shares_outstanding(payload, "NVDA") == payload


def test_shares_outstanding_validator_rejects_missing_data() -> None:
    payload = {"symbol": "NVDA", "status": "success", "data": []}
    with pytest.raises(PayloadValidationError):
        validate_shares_outstanding(payload, "NVDA")


def test_earnings_calendar_validator_accepts_sample() -> None:
    payload = _load_sample("earnings_calendar")
    assert validate_earnings_calendar(payload, "GLOBAL") == payload


def test_earnings_calendar_validator_rejects_missing_entries() -> None:
    payload = {"earningsCalendar": []}
    with pytest.raises(PayloadValidationError):
        validate_earnings_calendar(payload, "GLOBAL")


def test_transcript_validator_accepts_sample() -> None:
    payload = _load_sample("earnings_call_transcript_NVDA_2024Q3")
    assert validate_transcript(payload, "NVDA") == payload


def test_transcript_validator_rejects_missing_transcript() -> None:
    payload = {"symbol": "NVDA", "quarter": "2025Q3"}
    with pytest.raises(PayloadValidationError):
        validate_transcript(payload, "NVDA")


def test_transcript_run_accepts_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    async def fake_run(symbols, request_param_overrides=None):
        calls.append({
            "symbols": list(symbols or []),
            "overrides": request_param_overrides,
        })

    monkeypatch.setattr(
        "src.ingestion.alpha_vantage.earnings_call_transcript._RUNNER.run",
        fake_run,
    )

    asyncio.run(run_transcript(["NVDA"], quarter="2026Q4"))

    assert calls[0]["overrides"] == {"quarter": "2026Q4"}
