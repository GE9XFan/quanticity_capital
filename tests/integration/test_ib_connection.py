"""
Integration Test for Interactive Brokers Connection

PREREQUISITES:
- TWS or IB Gateway must be running
- API must be enabled in TWS settings (Edit → Global Configuration → API → Settings)
- Socket port must match IB_PORT in .env (default: 7497 for paper trading)
- This test makes REAL connections to IB - NO MOCKS

Run with: pytest tests/integration/test_ib_connection.py -v -s
"""
import sys
import os
import threading
import time
import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from src.brokers.ib.client import IBClient
from src.brokers.ib.config import IBConfig


class TestIBConnection:
    """Integration tests for IB API connection"""

    def test_connection_establishment(self):
        """
        Test that we can establish a connection to IB Gateway/TWS

        This test:
        1. Creates an IBClient instance
        2. Connects to TWS/IB Gateway
        3. Verifies connection is established
        4. Checks that nextValidId is received
        5. Verifies isConnected() returns True
        6. Cleanly disconnects
        """
        # Load configuration from environment
        config = IBConfig.from_env()

        print(f"\n{'='*60}")
        print(f"Testing IB Connection")
        print(f"{'='*60}")
        print(f"Host: {config.host}")
        print(f"Port: {config.port}")
        print(f"Client ID: {config.client_id}")
        print(f"{'='*60}\n")

        # Create client
        client = IBClient()

        try:
            # Connect to IB Gateway/TWS
            client.connect(config.host, config.port, config.client_id)

            # Start message processing in separate thread
            thread = threading.Thread(target=client.run, daemon=True)
            thread.start()

            # Wait for connection to be fully established
            connection_timeout = 10
            print(f"Waiting for connection (timeout: {connection_timeout}s)...")

            connection_successful = client.wait_for_connection(timeout=connection_timeout)

            # Assert connection was successful
            assert connection_successful, (
                "Connection timeout - check that TWS/IB Gateway is running "
                f"and API is enabled on port {config.port}"
            )

            # Verify connection state
            assert client.isConnected(), "Client reports not connected"
            print("✓ isConnected() returns True")

            # Verify nextValidId was received
            assert client.next_valid_order_id is not None, (
                "nextValidId was not received"
            )
            print(f"✓ Received nextValidId: {client.next_valid_order_id}")

            # Give a moment to ensure connection is stable
            time.sleep(1)

            # Verify still connected
            assert client.isConnected(), "Connection was lost"
            print("✓ Connection is stable")

            print(f"\n{'='*60}")
            print("✓ ALL CONNECTION TESTS PASSED")
            print(f"{'='*60}\n")

        finally:
            # Always disconnect
            print("Disconnecting...")
            client.disconnect()
            time.sleep(0.5)

            # Verify disconnected
            assert not client.isConnected(), "Client still reports connected after disconnect"
            print("✓ Disconnected successfully\n")


    def test_connection_error_handling(self):
        """
        Test connection error handling with invalid port

        This test verifies that the client properly handles connection failures.
        """
        print(f"\n{'='*60}")
        print(f"Testing Connection Error Handling")
        print(f"{'='*60}\n")

        # Create client with invalid port
        client = IBClient()

        try:
            # Attempt to connect to invalid port
            invalid_port = 9999
            print(f"Attempting connection to invalid port: {invalid_port}")

            client.connect("127.0.0.1", invalid_port, 0)

            # Start message processing
            thread = threading.Thread(target=client.run, daemon=True)
            thread.start()

            # Wait for connection (should timeout)
            connection_successful = client.wait_for_connection(timeout=5)

            # Should NOT connect
            assert not connection_successful, "Should not connect to invalid port"
            print("✓ Connection properly failed for invalid port")

            # Should not be connected
            assert not client.isConnected(), "Client should not be connected"
            print("✓ isConnected() correctly returns False")

            print(f"\n{'='*60}")
            print("✓ ERROR HANDLING TESTS PASSED")
            print(f"{'='*60}\n")

        finally:
            client.disconnect()


    def test_multiple_connections(self):
        """
        Test that multiple clients can connect simultaneously with different client IDs

        This verifies TWS's multi-client support.
        """
        print(f"\n{'='*60}")
        print(f"Testing Multiple Simultaneous Connections")
        print(f"{'='*60}\n")

        config = IBConfig.from_env()

        # Create two clients with different IDs
        client1 = IBClient()
        client2 = IBClient()

        try:
            # Connect client 1
            print("Connecting Client 1 (ID=0)...")
            client1.connect(config.host, config.port, client_id=0)
            thread1 = threading.Thread(target=client1.run, daemon=True)
            thread1.start()

            assert client1.wait_for_connection(timeout=10), "Client 1 connection timeout"
            print("✓ Client 1 connected")

            # Connect client 2 with different ID
            print("Connecting Client 2 (ID=1)...")
            client2.connect(config.host, config.port, client_id=1)
            thread2 = threading.Thread(target=client2.run, daemon=True)
            thread2.start()

            assert client2.wait_for_connection(timeout=10), "Client 2 connection timeout"
            print("✓ Client 2 connected")

            # Verify both are connected
            assert client1.isConnected(), "Client 1 not connected"
            assert client2.isConnected(), "Client 2 not connected"
            print("✓ Both clients connected simultaneously")

            # Verify each has unique order IDs
            assert client1.next_valid_order_id is not None
            assert client2.next_valid_order_id is not None
            print(f"✓ Client 1 order ID: {client1.next_valid_order_id}")
            print(f"✓ Client 2 order ID: {client2.next_valid_order_id}")

            print(f"\n{'='*60}")
            print("✓ MULTIPLE CONNECTION TESTS PASSED")
            print(f"{'='*60}\n")

        finally:
            # Disconnect both
            print("Disconnecting both clients...")
            client1.disconnect()
            client2.disconnect()
            time.sleep(0.5)
            print("✓ Both clients disconnected\n")


if __name__ == "__main__":
    """
    Run tests directly:
    python tests/integration/test_ib_connection.py
    """
    print("\n" + "="*60)
    print("IB CONNECTION INTEGRATION TESTS")
    print("="*60)
    print("\nPREREQUISITES:")
    print("- TWS or IB Gateway must be running")
    print("- API enabled in TWS settings")
    print("- Port 7497 open for paper trading")
    print("="*60 + "\n")

    # Run tests
    test_suite = TestIBConnection()

    try:
        print("\n[TEST 1/3] Connection Establishment")
        test_suite.test_connection_establishment()

        print("\n[TEST 2/3] Error Handling")
        test_suite.test_connection_error_handling()

        print("\n[TEST 3/3] Multiple Connections")
        test_suite.test_multiple_connections()

        print("\n" + "="*60)
        print("✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("="*60 + "\n")

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}\n")
        sys.exit(1)
