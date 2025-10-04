"""
Example: Query Stored Data from Redis and PostgreSQL

This example demonstrates how to query historical data
that has been stored by the monitoring application.

PREREQUISITES:
- Redis and PostgreSQL running
- Data has been collected by running src/main.py

USAGE:
    python examples/query_stored_data.py
"""

import os
import sys
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../'))

from src.storage import RedisClient, PostgresClient
from dotenv import load_dotenv

load_dotenv()


def main():
    """Query and display stored data."""
    account = os.getenv("IB_TEST_ACCOUNT")

    if not account:
        print("ERROR: Please set IB_TEST_ACCOUNT in .env")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"Querying Stored Data for Account: {account}")
    print(f"{'='*70}\n")

    # Initialize clients
    redis_client = RedisClient()
    postgres_client = PostgresClient()

    # ========================================================================
    # Redis Data (Real-time / Current State)
    # ========================================================================
    print("=" * 70)
    print("REDIS DATA (Real-time Cache)")
    print("=" * 70 + "\n")

    # Account Summary
    print("Account Summary:")
    print("-" * 50)
    summaries = redis_client.get_all_account_summaries(account)
    if summaries:
        for tag, data in sorted(summaries.items())[:10]:  # Show first 10
            print(f"  {tag:30s}: {data['value']:>15s} {data['currency']}")
    else:
        print("  No data (cache may have expired)")

    # Positions
    print(f"\nCurrent Positions:")
    print("-" * 50)
    positions = redis_client.get_all_positions(account)
    if positions:
        for contract_id, pos in positions.items():
            symbol = pos.get('symbol', 'N/A')
            qty = pos.get('position', 0)
            avg_cost = pos.get('avg_cost', 0)
            market_value = pos.get('market_value', 0)
            print(f"  {symbol:10s} | Qty: {qty:>12s} | Avg Cost: ${float(avg_cost):>10,.2f} | Value: ${float(market_value):>12,.2f}")
    else:
        print("  No positions (cache may have expired)")

    # P&L
    print(f"\nAccount P&L:")
    print("-" * 50)
    pnl = redis_client.get_account_pnl(account)
    if pnl:
        print(f"  Daily P&L:      ${float(pnl.get('daily_pnl', 0)):>12,.2f}")
        print(f"  Unrealized P&L: ${float(pnl.get('unrealized_pnl', 0)):>12,.2f}")
        print(f"  Realized P&L:   ${float(pnl.get('realized_pnl', 0)):>12,.2f}")
        print(f"  Last Update:    {pnl.get('last_update', 'N/A')}")
    else:
        print("  No P&L data (cache may have expired)")

    # ========================================================================
    # PostgreSQL Data (Historical)
    # ========================================================================
    print(f"\n\n{'='*70}")
    print("POSTGRESQL DATA (Historical)")
    print("=" * 70 + "\n")

    # Table counts
    print("Database Statistics:")
    print("-" * 50)
    counts = postgres_client.get_table_counts()
    for table, count in counts.items():
        print(f"  {table:25s}: {count:>10,} records")

    # Latest account summary
    print(f"\n\nLatest Account Summary (from PostgreSQL):")
    print("-" * 50)
    net_liq = postgres_client.get_latest_account_summary(account, "NetLiquidation")
    if net_liq:
        print(f"  Net Liquidation: ${float(net_liq['value']):,.2f} {net_liq['currency']}")
        print(f"  Timestamp: {net_liq['timestamp']}")
    else:
        print("  No NetLiquidation data")

    # Current positions
    print(f"\n\nCurrent Positions (from PostgreSQL view):")
    print("-" * 50)
    pg_positions = postgres_client.get_current_positions(account)
    if pg_positions:
        for pos in pg_positions[:10]:  # Show first 10
            print(f"  {pos['symbol']:10s} | {pos['sec_type']:5s} | Qty: {pos['position']:>12} | P&L: ${float(pos.get('unrealized_pnl') or 0):>10,.2f}")
    else:
        print("  No positions in database")

    # Latest EOD P&L
    print(f"\n\nEnd-of-Day P&L History (Last 7 days):")
    print("-" * 50)
    eod_pnl = postgres_client.get_latest_eod_pnl(account, limit=7)
    if eod_pnl:
        for record in eod_pnl:
            print(f"  {record['date']} | Daily: ${float(record.get('daily_pnl') or 0):>10,.2f} | Unrealized: ${float(record.get('unrealized_pnl') or 0):>10,.2f}")
    else:
        print("  No EOD P&L records")

    # Account summary history
    print(f"\n\nNet Liquidation History (Last 24 hours):")
    print("-" * 50)
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)
    history = postgres_client.get_account_summary_history(account, "NetLiquidation", start_time, end_time)
    if history:
        for record in history[:10]:  # Show first 10
            print(f"  {record['timestamp']} | ${float(record['value']):,.2f} {record['currency']}")
    else:
        print("  No history in last 24 hours")

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()
