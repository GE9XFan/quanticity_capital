"""
Example: Simple Account Summary Request

This example demonstrates how to:
1. Connect to IB Gateway
2. Request account summary data
3. Display the results
4. Disconnect

PREREQUISITES:
- TWS/IB Gateway running with API enabled on port 7497
- IB_TEST_ACCOUNT set in .env file

USAGE:
    python examples/simple_account_summary.py
"""

import os
import sys
import threading
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../'))

from src.brokers.ib import IBClient, IBConfig
from dotenv import load_dotenv

load_dotenv()


def main():
    """Simple account summary example."""
    # Get configuration
    config = IBConfig.from_env()
    account = os.getenv("IB_TEST_ACCOUNT")

    if not account:
        print("ERROR: Please set IB_TEST_ACCOUNT in .env")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Simple Account Summary Example")
    print(f"{'='*60}")
    print(f"Account: {account}")
    print(f"IB Gateway: {config.host}:{config.port}\n")

    # Create client (no storage for this simple example)
    client = IBClient()

    try:
        # Connect
        print("1. Connecting to IB Gateway...")
        client.connect(config.host, config.port, config.client_id)

        # Start message thread
        thread = threading.Thread(target=client.run, daemon=True)
        thread.start()

        # Wait for connection
        if not client.wait_for_connection(timeout=10):
            print("  ✗ Connection timeout")
            sys.exit(1)

        print("  ✓ Connected\n")

        # Request account summary
        print("2. Requesting account summary...")
        req_id = 9001
        client.req_account_summary(req_id, "All", tags=None)

        # Wait for data (IB sends initial snapshot immediately, then updates every 3 min)
        print("  Waiting for data (15 seconds)...\n")
        time.sleep(15)

        # Cancel subscription
        print("\n3. Cancelling subscription...")
        client.cancel_account_summary(req_id)

        print("  ✓ Complete\n")

    finally:
        # Disconnect
        print("4. Disconnecting...")
        client.disconnect()
        time.sleep(1)

    print(f"\n{'='*60}")
    print("NOTE: Data was printed to console by callbacks.")
    print("To store data, use Redis/PostgreSQL clients.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
