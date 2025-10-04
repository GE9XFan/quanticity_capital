"""
Main Application - Interactive Brokers Account & Portfolio Monitor

This application connects to Interactive Brokers and subscribes to:
- Account summary (every 3 minutes)
- Account updates (portfolio positions)
- Real-time P&L updates (~1 second)

Data is stored in:
- Redis: Real-time caching (TTL-based)
- PostgreSQL: Historical persistence (2-year retention)

PREREQUISITES:
1. TWS or IB Gateway running with API enabled
2. Redis running (localhost:6379)
3. PostgreSQL running with migrations applied
4. .env file configured with credentials

USAGE:
    python src/main.py

    Or with custom account:
    IB_TEST_ACCOUNT=DU123456 python src/main.py
"""

import os
import sys
import signal
import threading
import time
from datetime import datetime

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our modules
from src.brokers.ib import IBClient, IBConfig
from src.storage import RedisClient, PostgresClient
from src.services import AccountService


class IBAccountMonitor:
    """Main application class for IB account monitoring."""

    def __init__(self, account: str):
        """
        Initialize the monitor

        Args:
            account: IB account identifier (e.g., "DU123456")
        """
        self.account = account
        self.running = False

        # Initialize storage clients
        print("Initializing storage clients...")
        try:
            self.redis_client = RedisClient()
            print("  ✓ Redis connected")
        except Exception as e:
            print(f"  ✗ Redis connection failed: {e}")
            sys.exit(1)

        try:
            self.postgres_client = PostgresClient()
            print("  ✓ PostgreSQL connected")
        except Exception as e:
            print(f"  ✗ PostgreSQL connection failed: {e}")
            sys.exit(1)

        # Initialize service layer with optimized persistence intervals
        self.account_service = AccountService(
            redis_client=self.redis_client,
            postgres_client=self.postgres_client,
            summary_persist_interval=180,    # 3 minutes (matches IB update frequency)
            account_value_persist_interval=180,
            position_persist_interval=60,    # 1 minute
            pnl_persist_interval=60,         # 1 minute
        )

        # Initialize IB client
        self.ib_config = IBConfig.from_env()
        self.ib_client = IBClient(
            redis_client=self.redis_client,
            postgres_client=self.postgres_client,
            account_service=self.account_service,
        )

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\n\nReceived signal {signum}. Shutting down gracefully...")
        self.stop()
        sys.exit(0)

    def start(self):
        """Start the monitor."""
        print(f"\n{'='*70}")
        print(f"IB Account Monitor - Starting")
        print(f"{'='*70}")
        print(f"Account: {self.account}")
        print(f"IB Gateway: {self.ib_config.host}:{self.ib_config.port}")
        print(f"Client ID: {self.ib_config.client_id}")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")

        # Connect to IB
        print("Connecting to IB Gateway...")
        try:
            self.ib_client.connect(
                self.ib_config.host,
                self.ib_config.port,
                self.ib_config.client_id
            )
        except Exception as e:
            print(f"  ✗ Connection failed: {e}")
            print("\nMake sure TWS/IB Gateway is running with API enabled!")
            sys.exit(1)

        # Start message processing thread
        self.running = True
        thread = threading.Thread(target=self.ib_client.run, daemon=True)
        thread.start()

        # Wait for connection
        if not self.ib_client.wait_for_connection(timeout=10):
            print("  ✗ Connection timeout")
            sys.exit(1)

        print("  ✓ Connected to IB Gateway\n")

        # Start subscriptions
        self._start_subscriptions()

        # Main monitoring loop
        self._monitor_loop()

    def _start_subscriptions(self):
        """Start all data subscriptions."""
        print("Starting data subscriptions...")

        # 1. Account Summary (updates every 3 minutes)
        print("  → Account Summary (3-min updates)...")
        self.ib_client.req_account_summary(
            req_id=9001,
            group="All",
            tags=None  # All tags
        )

        # 2. Account Updates (portfolio positions)
        print("  → Account Updates (portfolio)...")
        self.ib_client.req_account_updates(
            subscribe=True,
            account=self.account
        )

        # 3. Positions (across all accounts)
        print("  → Positions...")
        self.ib_client.req_positions()

        # 4. Account-level P&L (real-time ~1 second)
        print("  → Account P&L (real-time)...")
        self.ib_client.req_pnl(
            req_id=9101,
            account=self.account,
            model_code=""
        )

        print("  ✓ All subscriptions started\n")
        print("Monitoring started. Data will be logged as it arrives.")
        print("Press Ctrl+C to stop...\n")

    def _monitor_loop(self):
        """Main monitoring loop - just keeps the app running."""
        try:
            # Print status every 30 seconds
            last_status_time = time.time()

            while self.running:
                current_time = time.time()

                # Print status update every 30 seconds
                if current_time - last_status_time >= 30:
                    self._print_status()
                    last_status_time = current_time

                time.sleep(1)

        except KeyboardInterrupt:
            print("\nShutdown requested...")
            self.stop()

    def _print_status(self):
        """Print current status summary."""
        print(f"\n{'─'*70}")
        print(f"Status Update - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'─'*70}")

        # Redis stats
        if self.redis_client:
            try:
                # Get summary data
                summaries = self.redis_client.get_all_account_summaries(self.account)
                net_liq = self.redis_client.get_account_summary(self.account, "NetLiquidation")

                if net_liq:
                    print(f"Net Liquidation: ${float(net_liq['value']):,.2f} {net_liq['currency']}")

                # Get positions
                positions = self.redis_client.get_all_positions(self.account)
                print(f"Positions: {len(positions)} contracts")

                # Get P&L
                pnl = self.redis_client.get_account_pnl(self.account)
                if pnl:
                    print(f"Daily P&L: ${float(pnl.get('daily_pnl', 0)):,.2f}")
                    print(f"Unrealized P&L: ${float(pnl.get('unrealized_pnl', 0)):,.2f}")
                    print(f"Realized P&L: ${float(pnl.get('realized_pnl', 0)):,.2f}")

            except Exception as e:
                print(f"Error getting Redis data: {e}")

        # PostgreSQL stats
        if self.postgres_client:
            try:
                counts = self.postgres_client.get_table_counts()
                print(f"\nDatabase records:")
                print(f"  - Contracts: {counts.get('contracts', 0)}")
                print(f"  - Account summary: {counts.get('account_summary', 0)}")
                print(f"  - Positions: {counts.get('positions', 0)}")
                print(f"  - Daily P&L: {counts.get('pnl_daily', 0)}")
            except Exception as e:
                print(f"Error getting PostgreSQL data: {e}")

        print(f"{'─'*70}\n")

    def stop(self):
        """Stop the monitor and cleanup."""
        print("\nStopping subscriptions...")
        self.running = False

        try:
            # Cancel subscriptions
            self.ib_client.cancel_account_summary(9001)
            self.ib_client.cancel_account_updates()
            self.ib_client.cancel_positions()
            self.ib_client.cancel_pnl(9101)
            print("  ✓ Subscriptions cancelled")
        except Exception as e:
            print(f"  ✗ Error cancelling subscriptions: {e}")

        # Disconnect
        try:
            self.ib_client.disconnect()
            print("  ✓ Disconnected from IB")
        except Exception as e:
            print(f"  ✗ Error disconnecting: {e}")

        print("\nShutdown complete.")


def main():
    """Main entry point."""
    # Get account from environment or use default
    account = os.getenv("IB_TEST_ACCOUNT")

    if not account:
        print("ERROR: IB_TEST_ACCOUNT environment variable not set!")
        print("\nPlease set your IB account in .env file:")
        print("  IB_TEST_ACCOUNT=DU123456")
        print("\nOr set it when running:")
        print("  IB_TEST_ACCOUNT=DU123456 python src/main.py")
        sys.exit(1)

    # Create and start monitor
    monitor = IBAccountMonitor(account=account)
    monitor.start()


if __name__ == "__main__":
    main()
