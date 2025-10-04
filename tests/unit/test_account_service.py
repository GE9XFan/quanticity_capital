"""Unit tests for AccountService change detection and persistence logic."""
from datetime import datetime, timedelta
from decimal import Decimal
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from src.brokers.ib.models import AccountSummaryTag, Position, AccountPnL, PositionPnL
from src.services.account_service import AccountService


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: int) -> None:
        self._now += timedelta(seconds=seconds)


class FakeRedis:
    def __init__(self) -> None:
        self.calls = []

    def store_account_summary(self, **kwargs):
        self.calls.append(("summary", kwargs))

    def store_position(self, **kwargs):
        self.calls.append(("position", kwargs))

    def store_account_pnl(self, **kwargs):
        self.calls.append(("account_pnl", kwargs))

    def store_position_pnl(self, **kwargs):
        self.calls.append(("position_pnl", kwargs))


class FakePostgres:
    def __init__(self) -> None:
        self.account_summary_calls = 0
        self.account_value_calls = 0
        self.position_calls = 0
        self.account_pnl_calls = 0
        self.position_pnl_calls = 0
        self.contracts = {}

    def insert_account_summary(self, **kwargs):
        self.account_summary_calls += 1

    def insert_account_value(self, **kwargs):
        self.account_value_calls += 1

    def upsert_contract(self, con_id, **kwargs):
        self.contracts[con_id] = kwargs

    def insert_position(self, **kwargs):
        self.position_calls += 1

    def insert_daily_pnl(self, **kwargs):
        self.account_pnl_calls += 1

    def insert_position_pnl(self, **kwargs):
        self.position_pnl_calls += 1


class ContractStub:
    def __init__(self, con_id: int, symbol: str = "AAPL") -> None:
        self.conId = con_id
        self.symbol = symbol
        self.secType = "STK"
        self.exchange = "NASDAQ"
        self.primaryExchange = "NASDAQ"
        self.currency = "USD"
        self.lastTradeDateOrContractMonth = ""
        self.strike = 0
        self.right = ""
        self.tradingClass = ""
        self.multiplier = ""
        self.localSymbol = symbol
        self.comboLegsDescrip = ""


def make_position(account: str = "DU123456", contract_id: int = 1, qty: Decimal = Decimal("1")) -> Position:
    return Position(
        account=account,
        contract_id=contract_id,
        position=qty,
        avg_cost=Decimal("100"),
        market_price=Decimal("150"),
        market_value=Decimal("150"),
        unrealized_pnl=Decimal("50"),
        realized_pnl=Decimal("0"),
        symbol="AAPL",
        sec_type="STK",
        exchange="NASDAQ",
    )


def test_account_summary_persists_on_change():
    clock = FakeClock(datetime(2024, 1, 1, 12, 0, 0))
    redis = FakeRedis()
    postgres = FakePostgres()
    service = AccountService(
        redis_client=redis,
        postgres_client=postgres,
        clock=clock.now,
        summary_persist_interval=300,
    )

    summary = AccountSummaryTag(
        account="DU123456",
        tag="NetLiquidation",
        value="100000",
        currency="USD",
    )

    service.handle_account_summary(req_id=1, summary=summary)
    assert postgres.account_summary_calls == 1

    # Same value within interval should not persist again
    service.handle_account_summary(req_id=1, summary=summary)
    assert postgres.account_summary_calls == 1

    # After interval, same value persists to maintain history
    clock.advance(600)
    service.handle_account_summary(req_id=1, summary=summary)
    assert postgres.account_summary_calls == 2


def test_position_snapshot_only_persists_when_changed():
    clock = FakeClock(datetime(2024, 1, 1, 12, 0, 0))
    redis = FakeRedis()
    postgres = FakePostgres()
    service = AccountService(
        redis_client=redis,
        postgres_client=postgres,
        clock=clock.now,
        position_persist_interval=120,
    )

    position = make_position()
    contract = ContractStub(con_id=position.contract_id)

    service.handle_portfolio_position(position, contract)
    assert postgres.position_calls == 1

    # Identical snapshot should not be persisted within interval
    service.handle_portfolio_position(position, contract)
    assert postgres.position_calls == 1

    # Change quantity triggers persistence
    new_position = position.model_copy(update={"position": Decimal("2")})
    service.handle_portfolio_position(new_position, contract)
    assert postgres.position_calls == 2


def test_account_pnl_persistence_respects_interval():
    clock = FakeClock(datetime(2024, 1, 1, 12, 0, 0))
    redis = FakeRedis()
    postgres = FakePostgres()
    service = AccountService(
        redis_client=redis,
        postgres_client=postgres,
        clock=clock.now,
        pnl_persist_interval=120,
    )

    pnl = AccountPnL(
        account="DU123456",
        daily_pnl=Decimal("100"),
        unrealized_pnl=Decimal("500"),
        realized_pnl=Decimal("50"),
    )

    service.handle_account_pnl(req_id=1, pnl=pnl, model_code="")
    assert postgres.account_pnl_calls == 1

    # No change -> no new insert until interval passes
    service.handle_account_pnl(req_id=1, pnl=pnl, model_code="")
    assert postgres.account_pnl_calls == 1

    clock.advance(300)
    service.handle_account_pnl(req_id=1, pnl=pnl, model_code="")
    assert postgres.account_pnl_calls == 2


def test_position_pnl_persists_on_change():
    clock = FakeClock(datetime(2024, 1, 1, 12, 0, 0))
    redis = FakeRedis()
    postgres = FakePostgres()
    service = AccountService(
        redis_client=redis,
        postgres_client=postgres,
        clock=clock.now,
        pnl_persist_interval=120,
    )

    pnl = PositionPnL(
        account="DU123456",
        contract_id=1,
        position=Decimal("1"),
        daily_pnl=Decimal("10"),
        unrealized_pnl=Decimal("15"),
        realized_pnl=Decimal("5"),
        value=Decimal("150"),
    )

    service.handle_position_pnl(req_id=1, pnl=pnl, model_code="")
    assert postgres.position_pnl_calls == 1

    # Changing value should be detected immediately
    updated = pnl.model_copy(update={"daily_pnl": Decimal("11")})
    service.handle_position_pnl(req_id=1, pnl=updated, model_code="")
    assert postgres.position_pnl_calls == 2
