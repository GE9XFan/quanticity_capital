"""
Account and Portfolio operations for Interactive Brokers API
Implements reqAccountSummary and reqAccountUpdates
"""
from decimal import Decimal
from datetime import datetime
from typing import Optional, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ibapi.contract import Contract as IBContract
else:
    try:
        from ibapi.contract import Contract as IBContract
    except ImportError:  # pragma: no cover - handled by manual ibapi install
        IBContract = Any  # type: ignore[misc,assignment]

# Import our models and storage clients
from .models import (
    AccountSummaryTag,
    AccountValue,
    AccountPnL,
    PositionPnL,
    contract_from_ib,
    position_from_update_portfolio,
    position_from_position_callback
)


class AccountMixin:
    """
    Mixin for account and portfolio operations

    Methods:
    - reqAccountSummary: Subscribe to account summary
    - reqAccountUpdates: Subscribe to account updates
    - cancelAccountSummary: Cancel account summary subscription
    - cancelAccountUpdates: Cancel account updates subscription

    Callbacks (must be implemented in IBClient):
    - accountSummary: Receives account summary data
    - accountSummaryEnd: Signals end of account summary data
    - updateAccountValue: Receives account values
    - updatePortfolio: Receives portfolio updates
    - updateAccountTime: Receives account update time
    - accountDownloadEnd: Signals end of account download
    """

    def __init__(self):
        """Initialize account tracking"""
        # Storage will be initialized in IBClient or via service layer
        self.redis_client = None
        self.postgres_client = None
        self.account_service = None
        self.account_id = None  # Set from config

        # Track active subscriptions
        self.account_summary_active = False
        self.account_updates_active = False
        self.positions_active = False
        self.pnl_active = set()  # Track reqIds for account-level PnL
        self.pnl_single_active = set()  # Track reqIds for position-level PnL
        self.pnl_accounts = {}  # reqId -> (account, model_code)
        self.pnl_single_accounts = {}  # reqId -> (account, model_code, conId)

    # ========================================================================
    # Account Summary Methods
    # ========================================================================

    def req_account_summary(self, req_id: int, group: str = "All", tags: Optional[str] = None):
        """
        Request account summary subscription

        Args:
            req_id: Unique request identifier
            group: "All" or specific account group
            tags: Comma-separated tags or None for all tags

        Important:
        - Only 2 active subscriptions allowed at a time
        - Updates every 3 minutes (IB limitation)
        - Initial call returns all values, then only changes
        """
        if tags is None:
            # Import all tags from ibapi if available
            try:
                from ibapi.account_summary_tags import AccountSummaryTags
                tags = AccountSummaryTags.AllTags
            except:
                # Fallback to important tags
                tags = (
                    "NetLiquidation,TotalCashValue,BuyingPower,EquityWithLoanValue,"
                    "AvailableFunds,ExcessLiquidity,GrossPositionValue,RegTEquity,"
                    "RegTMargin,SMA,InitMarginReq,MaintMarginReq,Cushion,"
                    "DayTradesRemaining,Leverage"
                )

        print(f"Requesting account summary (reqId={req_id}, group={group})")
        # Methods from EClient mixin
        self.reqAccountSummary(req_id, group, tags)  # type: ignore[attr-defined]
        self.account_summary_active = True

    def cancel_account_summary(self, req_id: int):
        """
        Cancel account summary subscription

        Args:
            req_id: Request identifier used in reqAccountSummary
        """
        print(f"Cancelling account summary (reqId={req_id})")
        self.cancelAccountSummary(req_id)  # type: ignore[attr-defined]
        self.account_summary_active = False

    # ========================================================================
    # Account Updates Methods
    # ========================================================================

    def req_account_updates(self, subscribe: bool, account: str):
        """
        Subscribe to account updates

        Args:
            subscribe: True to start, False to stop
            account: Account identifier (e.g., "U123456")

        Important:
        - Only ONE account can be subscribed at a time
        - Updates every 3 minutes or on position change
        - Second subscription cancels the first
        """
        print(f"{'Starting' if subscribe else 'Stopping'} account updates for {account}")
        self.reqAccountUpdates(subscribe, account)  # type: ignore[attr-defined]
        self.account_updates_active = subscribe

        if subscribe:
            self.account_id = account

    def cancel_account_updates(self):
        """Cancel account updates subscription"""
        if self.account_id:
            self.req_account_updates(False, self.account_id)

    # ========================================================================
    # Positions Methods
    # ========================================================================

    def req_positions(self):
        """Request account positions across all accounts"""
        if self.positions_active:
            print("Positions subscription already active")
            return

        print("Requesting positions")
        self.reqPositions()  # type: ignore[attr-defined]
        self.positions_active = True

    def cancel_positions(self):
        """Cancel positions subscription"""
        if not self.positions_active:
            return

        print("Cancelling positions subscription")
        self.cancelPositions()  # type: ignore[attr-defined]
        self.positions_active = False

    # ========================================================================
    # PnL Methods
    # ========================================================================

    def req_pnl(self, req_id: int, account: str, model_code: str = ""):
        """Subscribe to account-level P&L updates"""
        print(f"Requesting account PnL (reqId={req_id}, account={account}, model={model_code})")
        self.reqPnL(req_id, account, model_code)  # type: ignore[attr-defined]
        self.pnl_active.add(req_id)
        self.pnl_accounts[req_id] = (account, model_code)

    def cancel_pnl(self, req_id: int):
        """Cancel account-level P&L subscription"""
        if req_id not in self.pnl_active:
            return

        print(f"Cancelling account PnL (reqId={req_id})")
        self.cancelPnL(req_id)  # type: ignore[attr-defined]
        self.pnl_active.discard(req_id)
        self.pnl_accounts.pop(req_id, None)

    def req_pnl_single(self, req_id: int, account: str, model_code: str, con_id: int):
        """Subscribe to position-level P&L updates"""
        print(
            "Requesting position PnL "
            f"(reqId={req_id}, account={account}, model={model_code}, conId={con_id})"
        )
        self.reqPnLSingle(req_id, account, model_code, con_id)  # type: ignore[attr-defined]
        self.pnl_single_active.add(req_id)
        self.pnl_single_accounts[req_id] = (account, model_code, con_id)

    def cancel_pnl_single(self, req_id: int):
        """Cancel position-level P&L subscription"""
        if req_id not in self.pnl_single_active:
            return

        print(f"Cancelling position PnL (reqId={req_id})")
        self.cancelPnLSingle(req_id)  # type: ignore[attr-defined]
        self.pnl_single_active.discard(req_id)
        self.pnl_single_accounts.pop(req_id, None)

    # ========================================================================
    # Callback Implementations - Account Summary
    # ========================================================================

    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
        """
        Receives account summary data

        IB API Callback from reqAccountSummary

        Args:
            reqId: Request identifier
            account: Account identifier
            tag: Summary tag (e.g., "NetLiquidation")
            value: Value as string
            currency: Currency code

        Storage Strategy:
        - Redis: Store with 180s TTL (3-minute updates)
        - PostgreSQL: Store if tag is in important list
        """
        print(f"Account Summary: {account} | {tag} = {value} {currency}")

        # Create model
        summary = AccountSummaryTag(
            account=account,
            tag=tag,
            value=value,
            currency=currency
        )

        # Store in Redis ALWAYS (real-time cache)
        if self.redis_client:
            print(f"  → Storing in Redis: {account} | {tag}")  # DEBUG
            success = self.redis_client.store_account_summary(
                account=account,
                tag=tag,
                value=value,
                currency=currency,
                ttl=180  # 3 minutes
            )
            print(f"  → Redis storage: {'✓' if success else '✗'}")  # DEBUG
        else:
            print(f"  → NO Redis client configured!")  # DEBUG

        # Delegate PostgreSQL to service layer (with deduplication)
        if self.account_service:
            handled = self.account_service.handle_account_summary(req_id=reqId, summary=summary)
            if handled:
                return  # Service stored in PostgreSQL

        # Fallback: Store in PostgreSQL if no service (important tags only)
        if self.postgres_client and summary.numeric_value is not None:
            important_tags = {
                "NetLiquidation", "TotalCashValue", "BuyingPower",
                "AvailableFunds", "ExcessLiquidity", "GrossPositionValue",
                "InitMarginReq", "MaintMarginReq", "Cushion", "Leverage"
            }

            if tag in important_tags:
                self.postgres_client.insert_account_summary(
                    account=account,
                    tag=tag,
                    value=summary.numeric_value,
                    currency=currency
                )

    def accountSummaryEnd(self, reqId: int):
        """
        Signals end of account summary data (initial callback only)

        Args:
            reqId: Request identifier
        """
        print(f"Account Summary End (reqId={reqId})")

    # ========================================================================
    # Callback Implementations - Account Updates
    # ========================================================================

    def updateAccountValue(self, key: str, val: str, currency: str, accountName: str):
        """
        Receives account values

        IB API Callback from reqAccountUpdates

        Args:
            key: Account value key (e.g., "NetLiquidation")
            val: Value as string
            currency: Currency code
            accountName: Account identifier

        Important:
        - Check for 'accountReady' key
        - If accountReady = false, subsequent values may be out of date
        """
        print(f"Account Value: {accountName} | {key} = {val} {currency}")

        # Check account ready status
        if key == "AccountReady" and val.lower() == "false":
            print("⚠️  WARNING: Account not ready - values may be incorrect")
            return

        # Create model (note: accountName maps to account)
        account_value = AccountValue(
            account=accountName,
            key=key,
            value=val,
            currency=currency
        )

        # Note: account_values not cached in Redis (too many keys)
        # Delegate to service layer for PostgreSQL storage with deduplication
        if self.account_service:
            handled = self.account_service.handle_account_value(account_value)
            if handled:
                return  # Service stored in PostgreSQL

        # Fallback: Store in PostgreSQL if no service
        if self.postgres_client:
            self.postgres_client.insert_account_value(
                account=accountName,
                key=key,
                value=val,
                currency=currency
            )

    def updatePortfolio(self, contract: IBContract, position: Decimal, marketPrice: float,
                       marketValue: float, averageCost: float, unrealizedPNL: float,
                       realizedPNL: float, accountName: str):
        """
        Receives portfolio updates

        IB API Callback from reqAccountUpdates

        Args:
            contract: Contract object
            position: Position size (Decimal)
            marketPrice: Current market price
            marketValue: Total market value
            averageCost: Average cost per unit (note: averageCost not avgCost!)
            unrealizedPNL: Unrealized P&L (note: PNL not Pnl!)
            realizedPNL: Realized P&L
            accountName: Account identifier

        Storage Strategy:
        - Redis: Store current position with 300s TTL
        - PostgreSQL: Store if position changed from last snapshot
        - PostgreSQL: Upsert contract details
        """
        print(f"Portfolio Update: {contract.symbol} ({contract.secType}) | "
              f"Position: {position} | Market Value: {marketValue}")

        # Convert to our model
        position_model = position_from_update_portfolio(
            account=accountName,
            contract=contract,
            position=position,
            market_price=marketPrice,
            market_value=marketValue,
            average_cost=averageCost,
            unrealized_pnl=unrealizedPNL,
            realized_pnl=realizedPNL
        )

        if self.account_service:
            handled = self.account_service.handle_portfolio_position(position_model, contract)
            if handled:
                return

        # Store contract details in PostgreSQL
        if self.postgres_client:
            contract_model = contract_from_ib(contract)
            self.postgres_client.upsert_contract(
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
                combo_legs_descrip=contract_model.combo_legs_descrip
            )

        # Store position in Redis (current state)
        # IMPORTANT: Use Pydantic model fields (already converted to Decimal) not raw IB floats
        if self.redis_client:
            position_data = {
                "symbol": contract.symbol,
                "sec_type": contract.secType,
                "exchange": contract.exchange,
                "position": str(position_model.position),
                "avg_cost": str(position_model.avg_cost),
                "market_price": str(position_model.market_price),
                "market_value": str(position_model.market_value),
                "unrealized_pnl": str(position_model.unrealized_pnl),
                "realized_pnl": str(position_model.realized_pnl),
                "timestamp": datetime.now().isoformat()
            }
            self.redis_client.store_position(
                account=accountName,
                contract_id=contract.conId,
                position_data=position_data,
                ttl=300  # 5 minutes
            )

        # Store position snapshot in PostgreSQL
        if self.postgres_client:
            self.postgres_client.insert_position(
                account=accountName,
                contract_id=contract.conId,
                position=position,
                avg_cost=Decimal(str(averageCost)),
                market_price=Decimal(str(marketPrice)),
                market_value=Decimal(str(marketValue)),
                unrealized_pnl=Decimal(str(unrealizedPNL)),
                realized_pnl=Decimal(str(realizedPNL)),
                symbol=contract.symbol,
                sec_type=contract.secType,
                exchange=contract.exchange
            )

    def updateAccountTime(self, timeStamp: str):
        """
        Receives account update timestamp

        Args:
            timeStamp: Last update time
        """
        print(f"Account Update Time: {timeStamp}")

    def accountDownloadEnd(self, accountName: str):
        """
        Signals end of account download

        Args:
            accountName: Account identifier
        """
        print(f"Account Download End: {accountName}")

    # ========================================================================
    # Callback Implementations - Positions (reqPositions)
    # ========================================================================

    def position(self, account: str, contract: IBContract, position: Decimal, avgCost: float):
        """Receives position update from reqPositions"""
        print(f"Position Update: {account} | {contract.symbol} = {position}")

        position_model = position_from_position_callback(
            account=account,
            contract=contract,
            position=position,
            avg_cost=avgCost
        )

        if self.account_service:
            handled = self.account_service.handle_position_snapshot(position_model, contract)
            if handled:
                return

        # Fallback storage if service not configured
        # IMPORTANT: Use Pydantic model fields (already converted to Decimal) not raw IB floats
        if self.redis_client:
            position_data = {
                "symbol": contract.symbol,
                "sec_type": contract.secType,
                "exchange": contract.exchange,
                "position": str(position_model.position),
                "avg_cost": str(position_model.avg_cost) if position_model.avg_cost is not None else None,
                "timestamp": datetime.now().isoformat()
            }
            self.redis_client.store_position(account=account, contract_id=contract.conId, position_data=position_data)

        if self.postgres_client:
            contract_model = contract_from_ib(contract)
            self.postgres_client.upsert_contract(
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
                combo_legs_descrip=contract_model.combo_legs_descrip
            )

            self.postgres_client.insert_position(
                account=account,
                contract_id=contract.conId,
                position=position,
                avg_cost=Decimal(str(avgCost)) if avgCost is not None else None,
                market_price=None,
                market_value=None,
                unrealized_pnl=None,
                realized_pnl=None,
                symbol=contract.symbol,
                sec_type=contract.secType,
                exchange=contract.exchange
            )

    def positionEnd(self):
        """Signals end of positions batch"""
        self.positions_active = False
        print("Positions download complete")

    # ========================================================================
    # Callback Implementations - PnL (reqPnL / reqPnLSingle)
    # ========================================================================

    def pnl(self, reqId: int, dailyPnL: float, unrealizedPnL: float, realizedPnL: float):
        """Receives account-level P&L updates"""
        account_info = self.pnl_accounts.get(reqId)
        if not account_info:
            print(f"PnL callback received for unknown reqId={reqId}")
            return

        account, model_code = account_info
        print(
            "Account PnL Update: "
            f"{account} (model={model_code}) | daily={dailyPnL} unrealized={unrealizedPnL} "
            f"realized={realizedPnL}"
        )

        pnl_model = AccountPnL(
            account=account,
            daily_pnl=Decimal(str(dailyPnL)) if dailyPnL is not None else None,
            unrealized_pnl=Decimal(str(unrealizedPnL)) if unrealizedPnL is not None else None,
            realized_pnl=Decimal(str(realizedPnL)) if realizedPnL is not None else None
        )

        if self.account_service:
            handled = self.account_service.handle_account_pnl(req_id=reqId, pnl=pnl_model, model_code=model_code)
            if handled:
                return

        if self.redis_client:
            self.redis_client.store_account_pnl(
                account=account,
                daily_pnl=pnl_model.daily_pnl,
                unrealized_pnl=pnl_model.unrealized_pnl,
                realized_pnl=pnl_model.realized_pnl
            )

        if self.postgres_client:
            self.postgres_client.insert_daily_pnl(
                account=account,
                pnl_date=datetime.now().date(),
                daily_pnl=pnl_model.daily_pnl,
                unrealized_pnl=pnl_model.unrealized_pnl,
                realized_pnl=pnl_model.realized_pnl,
                timestamp=datetime.now(),
                is_eod=False
            )

    def pnlSingle(self, reqId: int, pos: Decimal, dailyPnL: float,
                  unrealizedPnL: float, realizedPnL: float, value: float):
        """Receives position-level P&L updates"""
        account_info = self.pnl_single_accounts.get(reqId)
        if not account_info:
            print(f"PnLSingle callback received for unknown reqId={reqId}")
            return

        account, model_code, con_id = account_info
        print(
            "Position PnL Update: "
            f"{account} (conId={con_id}, model={model_code}) | pos={pos} value={value}"
        )

        pnl_model = PositionPnL(
            account=account,
            contract_id=con_id,
            position=pos if pos is not None else None,  # pos is already Decimal from IB
            daily_pnl=Decimal(str(dailyPnL)) if dailyPnL is not None else None,
            unrealized_pnl=Decimal(str(unrealizedPnL)) if unrealizedPnL is not None else None,
            realized_pnl=Decimal(str(realizedPnL)) if realizedPnL is not None else None,
            value=Decimal(str(value)) if value is not None else None
        )

        if self.account_service:
            handled = self.account_service.handle_position_pnl(req_id=reqId, pnl=pnl_model, model_code=model_code)
            if handled:
                return

        if self.redis_client:
            self.redis_client.store_position_pnl(
                account=account,
                contract_id=con_id,
                position=pnl_model.position,
                daily_pnl=pnl_model.daily_pnl,
                unrealized_pnl=pnl_model.unrealized_pnl,
                realized_pnl=pnl_model.realized_pnl,
                value=pnl_model.value
            )

        if self.postgres_client:
            self.postgres_client.insert_position_pnl(
                account=account,
                contract_id=con_id,
                position=pnl_model.position,
                daily_pnl=pnl_model.daily_pnl,
                unrealized_pnl=pnl_model.unrealized_pnl,
                realized_pnl=pnl_model.realized_pnl,
                value=pnl_model.value,
                timestamp=datetime.now()
            )
    # ========================================================================
    # Helper Methods
    # ========================================================================

    def set_storage_clients(self, redis_client, postgres_client):
        """
        Set storage clients

        Args:
            redis_client: RedisClient instance
            postgres_client: PostgresClient instance
        """
        self.redis_client = redis_client
        self.postgres_client = postgres_client
        if self.account_service:
            self.account_service.attach_storage(redis_client=redis_client, postgres_client=postgres_client)

    def set_account_service(self, service):
        """Attach an account service that orchestrates persistence"""
        self.account_service = service
        if service:
            service.attach_storage(redis_client=self.redis_client, postgres_client=self.postgres_client)

    def get_account_summary_from_cache(self, account: str, tag: str) -> Optional[dict]:
        """
        Get account summary from Redis cache

        Args:
            account: Account identifier
            tag: Summary tag

        Returns:
            Dict with value and currency, or None
        """
        if self.redis_client:
            return self.redis_client.get_account_summary(account, tag)
        return None

    def get_all_positions_from_cache(self, account: str) -> dict:
        """
        Get all positions from Redis cache

        Args:
            account: Account identifier

        Returns:
            Dict of {contract_id: position_data}
        """
        if self.redis_client:
            return self.redis_client.get_all_positions(account)
        return {}
