#!/usr/bin/env python
"""Place a small OPTIONS test trade in IBKR paper account to trigger execution events."""

import asyncio
from ib_insync import IB, Option, MarketOrder
import sys
from datetime import datetime, timedelta

async def place_test_trade():
    ib = IB()
    try:
        # Connect to TWS paper trading - use different client ID
        await ib.connectAsync('127.0.0.1', 7497, clientId=103)
        print("Connected to TWS - OPTIONS TRADING SYSTEM")

        # Create an SPY option contract
        # Use expiration about 3 weeks out for liquidity
        contract = Option('SPY', '20251017', 665, 'C', 'SMART')
        await ib.qualifyContractsAsync(contract)
        print(f"Option contract qualified: {contract}")

        # Create a small market order - 1 option contract
        order = MarketOrder('BUY', 1)

        # Place the order
        trade = ib.placeOrder(contract, order)
        print(f"Option order placed: {trade.order.orderId}")
        print(f"Contract: SPY {contract.strike} {contract.right} exp {contract.lastTradeDateOrContractMonth}")

        # Wait for fill
        await asyncio.sleep(3)

        # Check order status
        if trade.orderStatus.status == 'Filled':
            print(f"Option filled! Execution ID: {trade.fills[0].execution.execId if trade.fills else 'N/A'}")
            print(f"Fill price: ${trade.orderStatus.avgFillPrice} per contract")
            print(f"Commission: ${trade.fills[0].commissionReport.commission if trade.fills and trade.fills[0].commissionReport else 'N/A'}")
        else:
            print(f"Order status: {trade.orderStatus.status}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if ib.isConnected():
            ib.disconnect()
            print("Disconnected")

if __name__ == "__main__":
    asyncio.run(place_test_trade())