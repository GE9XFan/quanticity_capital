"""
Data models for Interactive Brokers account and portfolio data
All field names verified against IB API version 10.37.2
"""
from datetime import datetime
import decimal
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class AccountSummaryTag(BaseModel):
    """
    Account summary data from reqAccountSummary
    IB Callback: accountSummary(reqId, account, tag, value, currency)
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    account: str = Field(..., description="Account identifier from IB")
    tag: str = Field(..., description="Summary tag (e.g., 'NetLiquidation', 'BuyingPower')")
    value: str = Field(..., description="Value as string (will be converted for storage)")
    currency: str = Field(..., description="Currency code (e.g., 'USD')")
    timestamp: datetime = Field(default_factory=datetime.now, description="When this value was captured")

    @property
    def numeric_value(self) -> Optional[Decimal]:
        """Convert string value to Decimal if possible"""
        try:
            return Decimal(self.value)
        except (ValueError, TypeError, decimal.InvalidOperation):
            # Value is not numeric (e.g., "INDIVIDUAL", "true", etc.)
            return None


class AccountValue(BaseModel):
    """
    Account value from reqAccountUpdates → updateAccountValue
    IB Callback: updateAccountValue(key, val, currency, accountName)
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    account: str = Field(..., description="Account identifier (maps from accountName)")
    key: str = Field(..., description="Account value key (e.g., 'NetLiquidation', 'BuyingPower')")
    value: str = Field(..., description="Value as string (can be numeric or text)")
    currency: str = Field(..., description="Currency code")
    timestamp: datetime = Field(default_factory=datetime.now, description="When this value was captured")


class Contract(BaseModel):
    """
    Contract details from IB API Contract object
    Complete mapping of all contract fields
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    # Primary identifier
    con_id: int = Field(..., description="Contract ID from contract.conId", alias="conId")

    # Basic contract information
    symbol: str = Field(..., description="Ticker symbol from contract.symbol")
    sec_type: str = Field(..., description="Security type from contract.secType", alias="secType")
    exchange: str = Field(..., description="Exchange from contract.exchange")
    primary_exchange: Optional[str] = Field(None, description="Primary exchange from contract.primaryExchange", alias="primaryExchange")
    currency: str = Field(..., description="Currency from contract.currency")

    # Derivative-specific fields
    last_trade_date: Optional[str] = Field(None, description="From contract.lastTradeDateOrContractMonth", alias="lastTradeDateOrContractMonth")
    strike: Optional[Decimal] = Field(None, description="Strike price from contract.strike")
    right: Optional[str] = Field(None, description="Option right (P/C) from contract.right")
    trading_class: Optional[str] = Field(None, description="Trading class from contract.tradingClass", alias="tradingClass")
    multiplier: Optional[str] = Field(None, description="Contract multiplier from contract.multiplier")

    # Additional details
    local_symbol: Optional[str] = Field(None, description="Local symbol from contract.localSymbol", alias="localSymbol")
    combo_legs_descrip: Optional[str] = Field(None, description="Combo legs description", alias="comboLegsDescrip")

    # Metadata
    first_seen: datetime = Field(default_factory=datetime.now, description="When contract was first stored")
    last_updated: datetime = Field(default_factory=datetime.now, description="Last update timestamp")


class Position(BaseModel):
    """
    Position data from multiple sources:
    - reqAccountUpdates → updatePortfolio
    - reqPositions → position

    IB Callbacks:
      updatePortfolio(contract, position, marketPrice, marketValue, averageCost,
                      unrealizedPNL, realizedPNL, accountName)
      position(account, contract, position, avgCost)
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    # Account and contract
    account: str = Field(..., description="Account identifier")
    contract_id: int = Field(..., description="Contract ID from contract.conId")

    # Position details
    position: Decimal = Field(..., description="Position size (supports fractional shares)")
    avg_cost: Optional[Decimal] = Field(None, description="Average cost (from averageCost or avgCost)")

    # Market data (from updatePortfolio only)
    market_price: Optional[Decimal] = Field(None, description="Current market price")
    market_value: Optional[Decimal] = Field(None, description="Total market value")

    # PnL (from updatePortfolio only)
    unrealized_pnl: Optional[Decimal] = Field(None, description="Daily unrealized P&L")
    realized_pnl: Optional[Decimal] = Field(None, description="Daily realized P&L")

    # Denormalized contract info
    symbol: Optional[str] = Field(None, description="Symbol for quick access")
    sec_type: Optional[str] = Field(None, description="Security type for quick access")
    exchange: Optional[str] = Field(None, description="Exchange for quick access")

    # Timestamp
    timestamp: datetime = Field(default_factory=datetime.now, description="When this snapshot was captured")


class AccountPnL(BaseModel):
    """
    Account-level P&L from reqPnL
    IB Callback: pnl(reqId, dailyPnL, unrealizedPnL, realizedPnL)
    Update frequency: ~1 second
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    account: str = Field(..., description="Account identifier")
    daily_pnl: Optional[Decimal] = Field(None, description="Daily P&L (resets per TWS settings)")
    unrealized_pnl: Optional[Decimal] = Field(None, description="Total unrealized P&L since inception")
    realized_pnl: Optional[Decimal] = Field(None, description="Total realized P&L since inception")
    timestamp: datetime = Field(default_factory=datetime.now, description="When this P&L was captured")


class PositionPnL(BaseModel):
    """
    Position-level P&L from reqPnLSingle
    IB Callback: pnlSingle(reqId, pos, dailyPnL, unrealizedPnL, realizedPnL, value)
    Update frequency: ~1 second

    Note: IB API uses 'pos' not 'position'!
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    account: str = Field(..., description="Account identifier")
    contract_id: int = Field(..., description="Contract ID")
    position: Optional[Decimal] = Field(None, description="Current position size (from 'pos')")
    daily_pnl: Optional[Decimal] = Field(None, description="Daily P&L for this position")
    unrealized_pnl: Optional[Decimal] = Field(None, description="Unrealized P&L since inception")
    realized_pnl: Optional[Decimal] = Field(None, description="Realized P&L since inception")
    value: Optional[Decimal] = Field(None, description="Current market value of position")
    timestamp: datetime = Field(default_factory=datetime.now, description="When this P&L was captured")


# ============================================================================
# Helper Functions
# ============================================================================

def contract_from_ib(ib_contract) -> Contract:
    """
    Convert IB Contract object to our Contract model

    Args:
        ib_contract: Contract object from ibapi.contract.Contract

    Returns:
        Contract: Our Pydantic model
    """
    return Contract(
        conId=ib_contract.conId,
        symbol=ib_contract.symbol,
        secType=ib_contract.secType,
        exchange=ib_contract.exchange,
        primaryExchange=ib_contract.primaryExchange if ib_contract.primaryExchange else None,
        currency=ib_contract.currency,
        lastTradeDateOrContractMonth=ib_contract.lastTradeDateOrContractMonth if ib_contract.lastTradeDateOrContractMonth else None,
        strike=Decimal(str(ib_contract.strike)) if ib_contract.strike and ib_contract.strike != 0 else None,
        right=ib_contract.right if ib_contract.right else None,
        tradingClass=ib_contract.tradingClass if ib_contract.tradingClass else None,
        multiplier=ib_contract.multiplier if ib_contract.multiplier else None,
        localSymbol=ib_contract.localSymbol if ib_contract.localSymbol else None,
        comboLegsDescrip=ib_contract.comboLegsDescrip if hasattr(ib_contract, 'comboLegsDescrip') and ib_contract.comboLegsDescrip else None
    )


def position_from_update_portfolio(account: str, contract, position: Decimal,
                                   market_price: float, market_value: float,
                                   average_cost: float, unrealized_pnl: float,
                                   realized_pnl: float) -> Position:
    """
    Create Position model from updatePortfolio callback

    Args:
        account: Account name (maps from accountName)
        contract: IB Contract object
        position: Position size
        market_price: Current market price
        market_value: Total market value
        average_cost: Average cost (note: averageCost not avgCost)
        unrealized_pnl: Unrealized P&L (note: unrealizedPNL)
        realized_pnl: Realized P&L (note: realizedPNL)

    Returns:
        Position: Our Pydantic model
    """
    return Position(
        account=account,
        contract_id=contract.conId,
        position=position,
        avg_cost=Decimal(str(average_cost)),
        market_price=Decimal(str(market_price)),
        market_value=Decimal(str(market_value)),
        unrealized_pnl=Decimal(str(unrealized_pnl)),
        realized_pnl=Decimal(str(realized_pnl)),
        symbol=contract.symbol,
        sec_type=contract.secType,
        exchange=contract.exchange
    )


def position_from_position_callback(account: str, contract, position: Decimal,
                                    avg_cost: float) -> Position:
    """
    Create Position model from position callback

    Args:
        account: Account identifier
        contract: IB Contract object
        position: Position size
        avg_cost: Average cost (note: avgCost not averageCost)

    Returns:
        Position: Our Pydantic model
    """
    return Position(
        account=account,
        contract_id=contract.conId,
        position=position,
        avg_cost=Decimal(str(avg_cost)),
        symbol=contract.symbol,
        sec_type=contract.secType,
        exchange=contract.exchange
    )
