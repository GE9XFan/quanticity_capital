"""Business logic layer for IB account, position, and PnL data."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Callable, Dict, Optional, Tuple, Any

from src.brokers.ib.models import (
    AccountSummaryTag,
    AccountValue,
    Position,
    AccountPnL,
    PositionPnL,
    contract_from_ib,
)


@dataclass
class _CacheEntry:
    """Internal helper for change detection."""

    signature: Tuple[Any, ...]
    timestamp: datetime


class AccountService:
    """Co-ordinates storage of IB account, position, and PnL data."""

    def __init__(
        self,
        redis_client=None,
        postgres_client=None,
        *,
        clock: Optional[Callable[[], datetime]] = None,
        summary_persist_interval: int = 180,
        account_value_persist_interval: int = 180,
        position_persist_interval: int = 60,
        pnl_persist_interval: int = 60,
    ) -> None:
        self.redis = redis_client
        self.postgres = postgres_client
        self._clock = clock or datetime.utcnow

        self.summary_persist_interval = summary_persist_interval
        self.account_value_persist_interval = account_value_persist_interval
        self.position_persist_interval = position_persist_interval
        self.pnl_persist_interval = pnl_persist_interval

        self._last_summary: Dict[str, Dict[str, _CacheEntry]] = defaultdict(dict)
        self._last_value: Dict[str, Dict[str, _CacheEntry]] = defaultdict(dict)
        self._last_position: Dict[Tuple[str, int], _CacheEntry] = {}
        self._last_account_pnl: Dict[str, _CacheEntry] = {}
        self._last_position_pnl: Dict[Tuple[str, int], _CacheEntry] = {}

        self._important_summary_tags = {
            "NetLiquidation",
            "TotalCashValue",
            "BuyingPower",
            "AvailableFunds",
            "ExcessLiquidity",
            "GrossPositionValue",
            "InitMarginReq",
            "MaintMarginReq",
            "Cushion",
            "Leverage",
        }

    # ------------------------------------------------------------------
    # Attachment helpers
    # ------------------------------------------------------------------

    def attach_storage(self, *, redis_client=None, postgres_client=None) -> None:
        """Attach storage clients after initialisation."""

        if redis_client is not None:
            self.redis = redis_client
        if postgres_client is not None:
            self.postgres = postgres_client

    # ------------------------------------------------------------------
    # Account summary / value handlers
    # ------------------------------------------------------------------

    def handle_account_summary(self, *, req_id: int, summary: AccountSummaryTag) -> bool:
        now = self._now()

        if self.redis:
            self.redis.store_account_summary(
                account=summary.account,
                tag=summary.tag,
                value=summary.value,
                currency=summary.currency,
            )

        persisted = False
        numeric_value = summary.numeric_value

        if (
            self.postgres
            and numeric_value is not None
            and summary.tag in self._important_summary_tags
        ):
            last_entry = self._last_summary[summary.account].get(summary.tag)
            signature = (numeric_value,)
            if self._should_persist(last_entry, signature, now, self.summary_persist_interval):
                self.postgres.insert_account_summary(
                    account=summary.account,
                    tag=summary.tag,
                    value=numeric_value,
                    currency=summary.currency,
                )
                self._last_summary[summary.account][summary.tag] = _CacheEntry(
                    signature=signature,
                    timestamp=now,
                )
                persisted = True

        return self._handled(persisted)

    def handle_account_value(self, account_value: AccountValue) -> bool:
        now = self._now()

        if self.redis:
            # These values are not cached in Redis in current design to avoid
            # sprawling keys. Future enhancement could mirror summaries.
            pass

        persisted = False
        if self.postgres:
            last_entry = self._last_value[account_value.account].get(account_value.key)
            signature = (account_value.value, account_value.currency)
            if self._should_persist(last_entry, signature, now, self.account_value_persist_interval):
                self.postgres.insert_account_value(
                    account=account_value.account,
                    key=account_value.key,
                    value=account_value.value,
                    currency=account_value.currency,
                )
                self._last_value[account_value.account][account_value.key] = _CacheEntry(
                    signature=signature,
                    timestamp=now,
                )
                persisted = True

        return self._handled(persisted)

    # ------------------------------------------------------------------
    # Position handlers
    # ------------------------------------------------------------------

    def handle_portfolio_position(self, position: Position, contract) -> bool:
        now = self._now()
        contract_model = contract_from_ib(contract)

        if self.redis:
            payload = {
                "symbol": contract_model.symbol,
                "sec_type": contract_model.sec_type,
                "exchange": contract_model.exchange,
                "position": str(position.position),
                "avg_cost": str(position.avg_cost) if position.avg_cost is not None else None,
                "market_price": str(position.market_price) if position.market_price is not None else None,
                "market_value": str(position.market_value) if position.market_value is not None else None,
                "unrealized_pnl": str(position.unrealized_pnl) if position.unrealized_pnl is not None else None,
                "realized_pnl": str(position.realized_pnl) if position.realized_pnl is not None else None,
                "timestamp": now.isoformat(),
            }
            self.redis.store_position(
                account=position.account,
                contract_id=position.contract_id,
                position_data=payload,
            )

        persisted = False
        if self.postgres:
            self.postgres.upsert_contract(
                con_id=contract_model.con_id,
                symbol=contract_model.symbol,
                sec_type=contract_model.sec_type,
                exchange=contract_model.exchange,
                primary_exchange=contract_model.primary_exchange,
                currency=contract_model.currency,
                last_trade_date=contract_model.last_trade_date,
                strike=contract_model.strike,
                right=contract_model.right,
                trading_class=contract_model.trading_class,
                multiplier=contract_model.multiplier,
                local_symbol=contract_model.local_symbol,
                combo_legs_descrip=contract_model.combo_legs_descrip,
            )

            persisted = self._persist_position_snapshot(position, now)

        return self._handled(persisted)

    def handle_position_snapshot(self, position: Position, contract) -> bool:
        now = self._now()
        contract_model = contract_from_ib(contract)

        if self.redis:
            payload = {
                "symbol": contract_model.symbol,
                "sec_type": contract_model.sec_type,
                "exchange": contract_model.exchange,
                "position": str(position.position),
                "avg_cost": str(position.avg_cost) if position.avg_cost is not None else None,
                "timestamp": now.isoformat(),
            }
            self.redis.store_position(
                account=position.account,
                contract_id=position.contract_id,
                position_data=payload,
            )

        persisted = False
        if self.postgres:
            self.postgres.upsert_contract(
                con_id=contract_model.con_id,
                symbol=contract_model.symbol,
                sec_type=contract_model.sec_type,
                exchange=contract_model.exchange,
                primary_exchange=contract_model.primary_exchange,
                currency=contract_model.currency,
                last_trade_date=contract_model.last_trade_date,
                strike=contract_model.strike,
                right=contract_model.right,
                trading_class=contract_model.trading_class,
                multiplier=contract_model.multiplier,
                local_symbol=contract_model.local_symbol,
                combo_legs_descrip=contract_model.combo_legs_descrip,
            )

            persisted = self._persist_position_snapshot(position, now)

        return self._handled(persisted)

    def _persist_position_snapshot(self, position: Position, now: datetime) -> bool:
        key = (position.account, position.contract_id)
        signature = (
            position.position,
            position.avg_cost,
            position.market_price,
            position.market_value,
            position.unrealized_pnl,
            position.realized_pnl,
        )

        last_entry = self._last_position.get(key)
        if not self._should_persist(last_entry, signature, now, self.position_persist_interval):
            return False

        self.postgres.insert_position(
            account=position.account,
            contract_id=position.contract_id,
            position=position.position,
            avg_cost=position.avg_cost,
            market_price=position.market_price,
            market_value=position.market_value,
            unrealized_pnl=position.unrealized_pnl,
            realized_pnl=position.realized_pnl,
            symbol=position.symbol,
            sec_type=position.sec_type,
            exchange=position.exchange,
        )

        self._last_position[key] = _CacheEntry(signature=signature, timestamp=now)
        return True

    # ------------------------------------------------------------------
    # PnL handlers
    # ------------------------------------------------------------------

    def handle_account_pnl(self, *, req_id: int, pnl: AccountPnL, model_code: str) -> bool:
        now = self._now()

        if self.redis:
            self.redis.store_account_pnl(
                account=pnl.account,
                daily_pnl=pnl.daily_pnl,
                unrealized_pnl=pnl.unrealized_pnl,
                realized_pnl=pnl.realized_pnl,
            )

        persisted = False
        signature = (
            pnl.daily_pnl,
            pnl.unrealized_pnl,
            pnl.realized_pnl,
        )

        if self.postgres:
            last_entry = self._last_account_pnl.get(pnl.account)
            if self._should_persist(last_entry, signature, now, self.pnl_persist_interval):
                self.postgres.insert_daily_pnl(
                    account=pnl.account,
                    pnl_date=date.today(),
                    daily_pnl=pnl.daily_pnl,
                    unrealized_pnl=pnl.unrealized_pnl,
                    realized_pnl=pnl.realized_pnl,
                    timestamp=now,
                    is_eod=False,
                )
                self._last_account_pnl[pnl.account] = _CacheEntry(
                    signature=signature,
                    timestamp=now,
                )
                persisted = True

        return self._handled(persisted)

    def handle_position_pnl(self, *, req_id: int, pnl: PositionPnL, model_code: str) -> bool:
        now = self._now()

        if self.redis:
            self.redis.store_position_pnl(
                account=pnl.account,
                contract_id=pnl.contract_id,
                position=pnl.position,
                daily_pnl=pnl.daily_pnl,
                unrealized_pnl=pnl.unrealized_pnl,
                realized_pnl=pnl.realized_pnl,
                value=pnl.value,
            )

        persisted = False
        if self.postgres:
            key = (pnl.account, pnl.contract_id)
            signature = (
                pnl.position,
                pnl.daily_pnl,
                pnl.unrealized_pnl,
                pnl.realized_pnl,
                pnl.value,
            )
            last_entry = self._last_position_pnl.get(key)
            if self._should_persist(last_entry, signature, now, self.pnl_persist_interval):
                self.postgres.insert_position_pnl(
                    account=pnl.account,
                    contract_id=pnl.contract_id,
                    position=pnl.position,
                    daily_pnl=pnl.daily_pnl,
                    unrealized_pnl=pnl.unrealized_pnl,
                    realized_pnl=pnl.realized_pnl,
                    value=pnl.value,
                    timestamp=now,
                )
                self._last_position_pnl[key] = _CacheEntry(
                    signature=signature,
                    timestamp=now,
                )
                persisted = True

        return self._handled(persisted)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _handled(self, persisted: bool) -> bool:
        """
        Return whether data was actually handled (persisted) by this service.

        Returns False if data wasn't persisted (due to deduplication), allowing
        the callback to handle storage directly. This ensures no data is lost.
        """
        return persisted

    def _now(self) -> datetime:
        return self._clock()

    @staticmethod
    def _should_persist(
        last_entry: Optional[_CacheEntry],
        signature: Tuple[Any, ...],
        now: datetime,
        interval_seconds: int,
    ) -> bool:
        if last_entry is None:
            return True

        if signature != last_entry.signature:
            return True

        return (now - last_entry.timestamp) >= timedelta(seconds=interval_seconds)

