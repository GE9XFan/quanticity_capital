"""
Interactive Brokers API Client
Implements connection handling following IB's official connectivity guide
"""
import threading
import time
from ibapi.client import EClient
from ibapi.wrapper import EWrapper

# Import AccountMixin for account and portfolio operations
from .account import AccountMixin


class IBClient(AccountMixin, EWrapper, EClient):
    """
    IB API Client combining EWrapper (callbacks) and EClient (requests)
    Now includes AccountMixin for account and portfolio operations

    CRITICAL: AccountMixin MUST come FIRST in inheritance order!
    Python MRO (Method Resolution Order) goes left-to-right. If EWrapper
    comes first, its default (empty) callbacks override our implementations!

    Connection Flow (Python API):
    1. connect() - establish socket connection (EReader thread auto-created)
    2. connectAck() - callback confirms connection
    3. run() - process message queue in infinite loop
    4. nextValidId() - signals ready to send messages

    Account Operations:
    - reqAccountSummary: Subscribe to account summary
    - reqAccountUpdates: Subscribe to account updates and portfolio

    Note: In Python, EReader is automatically handled by EClient.connect()
    """

    def __init__(self, redis_client=None, postgres_client=None, account_service=None):
        """
        Initialize IB Client

        Args:
            redis_client: Optional RedisClient instance for caching
            postgres_client: Optional PostgresClient instance for persistence
            account_service: Optional AccountService for coordinated storage
        """
        AccountMixin.__init__(self)
        EClient.__init__(self, wrapper=self)

        # Connection state
        self.next_valid_order_id = None
        self.connected_event = threading.Event()

        # Threading
        self.reader_thread = None
        self.is_running = False

        # Storage clients
        if redis_client or postgres_client:
            self.set_storage_clients(redis_client, postgres_client)

        # Optional service layer for orchestration
        if account_service:
            self.set_account_service(account_service)

    def connect(self, host: str, port: int, client_id: int):
        """
        Establish connection to TWS/IB Gateway

        Args:
            host: IP address (usually "127.0.0.1")
            port: Socket port (7497 for paper, 7496 for live)
            client_id: Unique client identifier (0-31)
        """
        print(f"Connecting to IB Gateway at {host}:{port} with client_id={client_id}...")
        super().connect(host, port, client_id)

    def run(self):
        """
        Main message processing loop - uses inherited EClient.run()

        Note: In Python API, EReader thread is automatically created by connect()
        The parent EClient.run() handles all message processing from the queue
        """
        self.is_running = True
        super().run()  # Use EClient's built-in run() method

    def disconnect(self):
        """Disconnect from TWS/IB Gateway"""
        self.is_running = False
        super().disconnect()
        print("Disconnected from IB Gateway")

    # ========== EWrapper Callbacks ==========

    def connectAck(self):
        """Called when connection is established"""
        print("✓ API Connection Established")

    def nextValidId(self, orderId: int):
        """
        Called after successful connection - signals ready to send messages

        Args:
            orderId: Next valid order ID for this session
        """
        self.next_valid_order_id = orderId
        print(f"✓ Connection Ready - Next Valid Order ID: {orderId}")
        self.connected_event.set()

    def connectionClosed(self):
        """Called when connection is lost"""
        print("✗ API Connection Closed")
        self.connected_event.clear()
        self.is_running = False

    def error(self, reqId: int, errorCode: int = None, errorString: str = "", errorTime: str = "", advancedOrderRejectJson: str = ""):
        """
        Handle errors and messages from TWS

        Args:
            reqId: Request ID
            errorCode: Error code
            errorString: Error message
            errorTime: Error timestamp (new in API 10.37+)
            advancedOrderRejectJson: Advanced order rejection details

        Common error codes:
        - 502: Cannot connect to TWS (not running or wrong port)
        - 507: Bad message / socket connection broken
        - -1: Socket exception (C#)
        """
        # Handle different signature variants
        if errorCode is None:
            # Old signature: error(reqId, errorString)
            print(f"IB Error: {errorString}")
            return

        if errorCode == 502:
            print(f"✗ ERROR {errorCode}: {errorString}")
            print("  → Check that TWS/IB Gateway is running with API enabled")
        elif errorCode in [507, -1]:
            print(f"✗ ERROR {errorCode}: Socket connection broken - {errorString}")
        else:
            # Many "errors" are just informational messages
            print(f"IB Message [{errorCode}]: {errorString}")

    # ========== Helper Methods ==========

    def wait_for_connection(self, timeout: int = 10):
        """
        Wait for connection to be fully established

        Args:
            timeout: Maximum seconds to wait

        Returns:
            bool: True if connected, False if timeout
        """
        return self.connected_event.wait(timeout)
