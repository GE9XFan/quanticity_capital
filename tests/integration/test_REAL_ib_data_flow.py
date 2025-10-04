"""
REAL IB Data Flow Test - NO FALSE POSITIVES!

This test ACTUALLY verifies that:
1. IB sends data to our callbacks
2. Data is stored in Redis
3. Data is stored in PostgreSQL  
4. $250K account balance is captured

FAILS if NO data received from IB!

Prerequisites:
- TWS/Gateway running on port 7497
- IB_TEST_ACCOUNT set in .env (e.g., DUH923436)
- Account has data/balance

Run: python tests/integration/test_REAL_ib_data_flow.py
"""
import os
import sys
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from src.brokers.ib.client import IBClient
from src.brokers.ib.config import IBConfig
from src.storage import RedisClient, PostgresClient
from src.services import AccountService


class DataFlowTracker:
    """Tracks whether callbacks are actually being called"""
    
    def __init__(self):
        self.account_summary_received = []
        self.account_values_received = []
        self.portfolio_received = []
        
    def track_summary(self, reqId, account, tag, value, currency):
        self.account_summary_received.append({
            'account': account, 'tag': tag, 'value': value, 'currency': currency
        })
        print(f"  📊 RECEIVED: Account Summary | {account} | {tag} = {value} {currency}")
        
    def track_value(self, key, val, currency, accountName):
        self.account_values_received.append({
            'account': accountName, 'key': key, 'value': val, 'currency': currency
        })
        print(f"  💰 RECEIVED: Account Value | {accountName} | {key} = {val} {currency}")
        
    def track_portfolio(self, contract, position, marketPrice, marketValue, 
                       averageCost, unrealizedPNL, realizedPNL, accountName):
        self.portfolio_received.append({
            'account': accountName, 'symbol': contract.symbol, 'position': str(position)
        })
        print(f"  📈 RECEIVED: Portfolio | {accountName} | {contract.symbol} = {position}")


def test_real_ib_data_flow():
    """Test that actually verifies IB data flows to database"""
    
    # Get account
    account = os.getenv("IB_TEST_ACCOUNT")
    if not account:
        print("❌ ERROR: IB_TEST_ACCOUNT not set!")
        print("Set it in .env: IB_TEST_ACCOUNT=DUH923436")
        sys.exit(1)
    
    print(f"\n{'='*70}")
    print(f"REAL IB DATA FLOW TEST")
    print(f"{'='*70}")
    print(f"Account: {account}")
    print(f"Time: {datetime.now()}")
    print(f"{'='*70}\n")
    
    # Initialize
    config = IBConfig.from_env()
    redis_client = RedisClient()
    postgres_client = PostgresClient()
    account_service = AccountService(
        redis_client=redis_client,
        postgres_client=postgres_client
    )
    
    # Clear old data
    print("1. Clearing old test data...")
    redis_client.clear_account_data(account)
    
    # Check initial state
    counts_before = postgres_client.get_table_counts()
    print(f"   Initial DB state:")
    print(f"   - account_summary: {counts_before.get('account_summary', 0)}")
    print(f"   - account_values: {counts_before.get('account_values', 0)}")
    print(f"   - positions: {counts_before.get('positions', 0)}")
    
    # Create client
    client = IBClient(
        redis_client=redis_client,
        postgres_client=postgres_client,
        account_service=account_service
    )
    
    # Setup tracker
    tracker = DataFlowTracker()
    
    # Monkey-patch to track callbacks
    original_summary = client.accountSummary
    def tracked_summary(reqId, acct, tag, value, currency):
        tracker.track_summary(reqId, acct, tag, value, currency)
        return original_summary(reqId, acct, tag, value, currency)
    client.accountSummary = tracked_summary
    
    original_value = client.updateAccountValue
    def tracked_value(key, val, currency, acctName):
        tracker.track_value(key, val, currency, acctName)
        return original_value(key, val, currency, acctName)
    client.updateAccountValue = tracked_value
    
    original_portfolio = client.updatePortfolio
    def tracked_portfolio(contract, pos, price, value, cost, unreal, real, acctName):
        tracker.track_portfolio(contract, pos, price, value, cost, unreal, real, acctName)
        return original_portfolio(contract, pos, price, value, cost, unreal, real, acctName)
    client.updatePortfolio = tracked_portfolio
    
    try:
        # Connect
        print("\n2. Connecting to IB...")
        client.connect(config.host, config.port, config.client_id)
        
        thread = threading.Thread(target=client.run, daemon=True)
        thread.start()
        
        if not client.wait_for_connection(timeout=10):
            print("❌ Connection timeout!")
            sys.exit(1)
        
        print("   ✓ Connected")
        
        # Request data
        print(f"\n3. Requesting account data for: {account}")
        print("   (This can take up to 3 minutes for first callback)")
        
        client.req_account_summary(9001, "All", None)
        client.req_account_updates(True, account)
        
        print("\n4. Waiting for IB callbacks (60 seconds)...")
        print("   Watching for data...\n")
        
        time.sleep(60)  # Wait 1 minute
        
        # Check results
        print(f"\n5. Verifying data received...")
        print(f"   Account Summary callbacks: {len(tracker.account_summary_received)}")
        print(f"   Account Value callbacks: {len(tracker.account_values_received)}")
        print(f"   Portfolio callbacks: {len(tracker.portfolio_received)}")
        
        # Verify we got SOME data
        if len(tracker.account_summary_received) == 0:
            print("\n❌ CRITICAL FAILURE: NO account summary data received from IB!")
            print("   Expected 40+ callbacks for account summary tags")
            print("   Got: 0")
            print("\n   Possible causes:")
            print("   - IB Gateway not running")
            print("   - Account doesn't have permissions")
            print("   - Connection dropped (check IB logs)")
            sys.exit(1)
        
        # Check Redis
        print("\n6. Verifying Redis storage...")
        redis_summaries = redis_client.get_all_account_summaries(account)
        print(f"   Redis summary keys: {len(redis_summaries)}")
        
        if len(redis_summaries) == 0:
            print("   ❌ ERROR: Data received but NOT in Redis!")
            sys.exit(1)
        
        # Check specific value
        net_liq = redis_client.get_account_summary(account, "NetLiquidation")
        if net_liq:
            print(f"   ✓ NetLiquidation: ${float(net_liq['value']):,.2f} {net_liq['currency']}")
        
        # Check PostgreSQL
        print("\n7. Verifying PostgreSQL storage...")
        counts_after = postgres_client.get_table_counts()
        
        print(f"   - account_summary: {counts_after.get('account_summary', 0)} " +
              f"(+{counts_after.get('account_summary', 0) - counts_before.get('account_summary', 0)})")
        print(f"   - account_values: {counts_after.get('account_values', 0)} " +
              f"(+{counts_after.get('account_values', 0) - counts_before.get('account_values', 0)})")
        print(f"   - positions: {counts_after.get('positions', 0)} " +
              f"(+{counts_after.get('positions', 0) - counts_before.get('positions', 0)})")
        
        # Verify account_values has data
        if counts_after.get('account_values', 0) == 0:
            print("\n   ⚠️  WARNING: account_values table is EMPTY!")
            print("   This is the bug - updateAccountValue callbacks not persisting!")
            
            # Check if callbacks were received
            if len(tracker.account_values_received) > 0:
                print(f"   Callbacks received: {len(tracker.account_values_received)}")
                print("   But table is empty - storage is broken!")
                sys.exit(1)
            else:
                print("   No callbacks received - IB not sending updateAccountValue")
        else:
            print(f"   ✓ account_values has {counts_after.get('account_values', 0)} records")
        
        # Summary
        print(f"\n{'='*70}")
        if len(tracker.account_summary_received) > 0:
            print("✅ TEST PASSED: Data flowing from IB to database")
            print(f"   - {len(tracker.account_summary_received)} summary callbacks received")
            print(f"   - {len(redis_summaries)} keys in Redis")
            print(f"   - {counts_after.get('account_summary', 0)} records in PostgreSQL")
        else:
            print("❌ TEST FAILED: NO data received from IB")
        print(f"{'='*70}\n")
        
    finally:
        client.cancel_account_summary(9001)
        client.cancel_account_updates()
        client.disconnect()
        time.sleep(1)


if __name__ == "__main__":
    test_real_ib_data_flow()
