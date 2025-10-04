"""
PostgreSQL client for storing historical account and portfolio data
Schema defined in migrations/001_initial_schema.sql
"""
import os
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


class PostgresClient:
    """
    PostgreSQL client for account and portfolio data persistence

    Tables:
    - contracts: Contract details
    - account_summary: Account summary snapshots
    - account_values: Account value snapshots
    - positions: Position snapshots
    - pnl_daily: Daily account P&L
    - pnl_positions: Position-level P&L
    """

    def __init__(self, connection_string: str = None):
        """
        Initialize PostgreSQL client

        Args:
            connection_string: PostgreSQL connection string
                             (defaults to DATABASE_URL env var)
        """
        self.connection_string = connection_string or os.getenv("DATABASE_URL")

        if not self.connection_string:
            # Build from individual components
            host = os.getenv("POSTGRES_HOST", "localhost")
            port = os.getenv("POSTGRES_PORT", "5432")
            database = os.getenv("POSTGRES_DB", "quanticity_capital")
            user = os.getenv("POSTGRES_USER", "postgres")
            password = os.getenv("POSTGRES_PASSWORD", "")

            self.connection_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"

        # Test connection
        try:
            conn = self._get_connection()
            conn.close()
            print("✓ PostgreSQL connected")
        except Exception as e:
            print(f"✗ PostgreSQL connection failed: {e}")
            raise

    def _get_connection(self):
        """Get database connection"""
        return psycopg2.connect(self.connection_string)

    # ========================================================================
    # Contract Methods
    # ========================================================================

    def upsert_contract(self, con_id: int, symbol: str, sec_type: str, exchange: str,
                       primary_exchange: Optional[str], currency: str,
                       last_trade_date: Optional[str] = None, strike: Optional[Decimal] = None,
                       right: Optional[str] = None, trading_class: Optional[str] = None,
                       multiplier: Optional[str] = None, local_symbol: Optional[str] = None,
                       combo_legs_descrip: Optional[str] = None):
        """
        Insert or update contract details

        Args:
            con_id: Contract ID
            symbol: Ticker symbol
            sec_type: Security type
            exchange: Exchange
            primary_exchange: Primary exchange
            currency: Currency
            last_trade_date: Last trade date (for derivatives)
            strike: Strike price (for options)
            right: P or C (for options)
            trading_class: Trading class
            multiplier: Contract multiplier
            local_symbol: Local symbol
            combo_legs_descrip: Combo legs description

        Returns:
            bool: True if successful
        """
        sql = """
        INSERT INTO contracts (
            con_id, symbol, sec_type, exchange, primary_exchange, currency,
            last_trade_date, strike, "right", trading_class, multiplier,
            local_symbol, combo_legs_descrip, first_seen, last_updated
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
        )
        ON CONFLICT (con_id) DO UPDATE SET
            symbol = EXCLUDED.symbol,
            sec_type = EXCLUDED.sec_type,
            exchange = EXCLUDED.exchange,
            primary_exchange = EXCLUDED.primary_exchange,
            currency = EXCLUDED.currency,
            last_trade_date = EXCLUDED.last_trade_date,
            strike = EXCLUDED.strike,
            "right" = EXCLUDED."right",
            trading_class = EXCLUDED.trading_class,
            multiplier = EXCLUDED.multiplier,
            local_symbol = EXCLUDED.local_symbol,
            combo_legs_descrip = EXCLUDED.combo_legs_descrip,
            last_updated = NOW()
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (
                        con_id, symbol, sec_type, exchange, primary_exchange, currency,
                        last_trade_date, strike, right, trading_class, multiplier,
                        local_symbol, combo_legs_descrip
                    ))
                    conn.commit()
            return True
        except Exception as e:
            print(f"Error upserting contract: {e}")
            return False

    def get_contract(self, con_id: int) -> Optional[Dict]:
        """
        Get contract by ID

        Args:
            con_id: Contract ID

        Returns:
            Contract data as dict, or None if not found
        """
        sql = "SELECT * FROM contracts WHERE con_id = %s"

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, (con_id,))
                    result = cur.fetchone()
                    return dict(result) if result else None
        except Exception as e:
            print(f"Error getting contract: {e}")
            return None

    # ========================================================================
    # Account Summary Methods
    # ========================================================================

    def insert_account_summary(self, account: str, tag: str, value: Decimal,
                              currency: str, timestamp: datetime = None):
        """
        Insert account summary snapshot

        Args:
            account: Account identifier
            tag: Summary tag
            value: Numeric value
            currency: Currency code
            timestamp: Snapshot timestamp (defaults to now)

        Returns:
            bool: True if successful
        """
        sql = """
        INSERT INTO account_summary (account, tag, value, currency, timestamp)
        VALUES (%s, %s, %s, %s, %s)
        """

        timestamp = timestamp or datetime.now()

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (account, tag, value, currency, timestamp))
                    conn.commit()
            return True
        except Exception as e:
            print(f"Error inserting account summary: {e}")
            return False

    def get_latest_account_summary(self, account: str, tag: str) -> Optional[Dict]:
        """
        Get most recent account summary for a tag

        Args:
            account: Account identifier
            tag: Summary tag

        Returns:
            Summary data as dict, or None if not found
        """
        sql = """
        SELECT * FROM account_summary
        WHERE account = %s AND tag = %s
        ORDER BY timestamp DESC
        LIMIT 1
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, (account, tag))
                    result = cur.fetchone()
                    return dict(result) if result else None
        except Exception as e:
            print(f"Error getting latest account summary: {e}")
            return None

    def get_account_summary_history(self, account: str, tag: str,
                                   start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Get account summary history for a tag

        Args:
            account: Account identifier
            tag: Summary tag
            start_date: Start datetime
            end_date: End datetime

        Returns:
            List of summary records
        """
        sql = """
        SELECT * FROM account_summary
        WHERE account = %s AND tag = %s
          AND timestamp BETWEEN %s AND %s
        ORDER BY timestamp DESC
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, (account, tag, start_date, end_date))
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            print(f"Error getting account summary history: {e}")
            return []

    # ========================================================================
    # Account Value Methods
    # ========================================================================

    def insert_account_value(self, account: str, key: str, value: str,
                            currency: str, timestamp: datetime = None):
        """
        Insert account value snapshot

        Args:
            account: Account identifier
            key: Account value key
            value: Value as string
            currency: Currency code
            timestamp: Snapshot timestamp (defaults to now)

        Returns:
            bool: True if successful
        """
        sql = """
        INSERT INTO account_values (account, key, value, currency, timestamp)
        VALUES (%s, %s, %s, %s, %s)
        """

        timestamp = timestamp or datetime.now()

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (account, key, value, currency, timestamp))
                    conn.commit()
            return True
        except Exception as e:
            print(f"Error inserting account value: {e}")
            return False

    # ========================================================================
    # Position Methods
    # ========================================================================

    def insert_position(self, account: str, contract_id: int, position: Decimal,
                       avg_cost: Optional[Decimal], market_price: Optional[Decimal],
                       market_value: Optional[Decimal], unrealized_pnl: Optional[Decimal],
                       realized_pnl: Optional[Decimal], symbol: Optional[str],
                       sec_type: Optional[str], exchange: Optional[str],
                       timestamp: datetime = None):
        """
        Insert position snapshot

        Args:
            account: Account identifier
            contract_id: Contract ID
            position: Position size
            avg_cost: Average cost
            market_price: Market price
            market_value: Market value
            unrealized_pnl: Unrealized P&L
            realized_pnl: Realized P&L
            symbol: Symbol (denormalized)
            sec_type: Security type (denormalized)
            exchange: Exchange (denormalized)
            timestamp: Snapshot timestamp (defaults to now)

        Returns:
            bool: True if successful
        """
        sql = """
        INSERT INTO positions (
            account, contract_id, position, avg_cost, market_price, market_value,
            unrealized_pnl, realized_pnl, symbol, sec_type, exchange, timestamp
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        timestamp = timestamp or datetime.now()

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (
                        account, contract_id, position, avg_cost, market_price, market_value,
                        unrealized_pnl, realized_pnl, symbol, sec_type, exchange, timestamp
                    ))
                    conn.commit()
            return True
        except Exception as e:
            print(f"Error inserting position: {e}")
            return False

    def get_current_positions(self, account: str) -> List[Dict]:
        """
        Get current positions (uses view)

        Args:
            account: Account identifier

        Returns:
            List of current positions
        """
        sql = "SELECT * FROM v_current_positions WHERE account = %s"

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, (account,))
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            print(f"Error getting current positions: {e}")
            return []

    # ========================================================================
    # PnL Methods
    # ========================================================================

    def insert_daily_pnl(self, account: str, pnl_date: date, daily_pnl: Optional[Decimal],
                        unrealized_pnl: Optional[Decimal], realized_pnl: Optional[Decimal],
                        timestamp: datetime = None, is_eod: bool = False):
        """
        Insert daily P&L snapshot

        Args:
            account: Account identifier
            pnl_date: Trading date
            daily_pnl: Daily P&L
            unrealized_pnl: Unrealized P&L
            realized_pnl: Realized P&L
            timestamp: Snapshot timestamp (defaults to now)
            is_eod: True if end-of-day snapshot

        Returns:
            bool: True if successful
        """
        # Different SQL for EOD vs real-time snapshots
        if is_eod:
            # EOD snapshots: UPSERT (only one per day)
            sql = """
            INSERT INTO pnl_daily (
                account, date, daily_pnl, unrealized_pnl, realized_pnl, timestamp, is_eod_snapshot
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (account, date) WHERE is_eod_snapshot = TRUE
            DO UPDATE SET
                daily_pnl = EXCLUDED.daily_pnl,
                unrealized_pnl = EXCLUDED.unrealized_pnl,
                realized_pnl = EXCLUDED.realized_pnl,
                timestamp = EXCLUDED.timestamp
            """
        else:
            # Real-time snapshots: Just insert (multiple per day allowed)
            sql = """
            INSERT INTO pnl_daily (
                account, date, daily_pnl, unrealized_pnl, realized_pnl, timestamp, is_eod_snapshot
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """

        timestamp = timestamp or datetime.now()

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (
                        account, pnl_date, daily_pnl, unrealized_pnl,
                        realized_pnl, timestamp, is_eod
                    ))
                    conn.commit()
            return True
        except Exception as e:
            print(f"Error inserting daily PnL: {e}")
            return False

    def insert_position_pnl(self, account: str, contract_id: int, position: Optional[Decimal],
                           daily_pnl: Optional[Decimal], unrealized_pnl: Optional[Decimal],
                           realized_pnl: Optional[Decimal], value: Optional[Decimal],
                           timestamp: datetime = None):
        """
        Insert position P&L snapshot

        Args:
            account: Account identifier
            contract_id: Contract ID
            position: Position size
            daily_pnl: Daily P&L
            unrealized_pnl: Unrealized P&L
            realized_pnl: Realized P&L
            value: Current market value
            timestamp: Snapshot timestamp (defaults to now)

        Returns:
            bool: True if successful
        """
        sql = """
        INSERT INTO pnl_positions (
            account, contract_id, position, daily_pnl, unrealized_pnl,
            realized_pnl, value, timestamp
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        timestamp = timestamp or datetime.now()

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (
                        account, contract_id, position, daily_pnl, unrealized_pnl,
                        realized_pnl, value, timestamp
                    ))
                    conn.commit()
            return True
        except Exception as e:
            print(f"Error inserting position PnL: {e}")
            return False

    def get_latest_eod_pnl(self, account: str, limit: int = 30) -> List[Dict]:
        """
        Get latest end-of-day P&L records

        Args:
            account: Account identifier
            limit: Number of records to retrieve

        Returns:
            List of EOD P&L records
        """
        sql = """
        SELECT * FROM v_latest_eod_pnl
        WHERE account = %s
        ORDER BY date DESC
        LIMIT %s
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, (account, limit))
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            print(f"Error getting latest EOD PnL: {e}")
            return []

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def test_connection(self) -> bool:
        """
        Test database connection

        Returns:
            bool: True if connected
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False

    def get_table_counts(self) -> Dict[str, int]:
        """
        Get row counts for all tables

        Returns:
            Dict of {table_name: row_count}
        """
        tables = [
            "contracts", "account_summary", "account_values",
            "positions", "pnl_daily", "pnl_positions"
        ]

        counts = {}
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    for table in tables:
                        cur.execute(f"SELECT COUNT(*) FROM {table}")
                        counts[table] = cur.fetchone()[0]
            return counts
        except Exception as e:
            print(f"Error getting table counts: {e}")
            return {}

    def cleanup_old_data(self):
        """
        Run cleanup function to remove old data (2 year retention)

        Returns:
            bool: True if successful
        """
        sql = "SELECT cleanup_old_data()"

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    conn.commit()
            print("Cleanup completed successfully")
            return True
        except Exception as e:
            print(f"Error running cleanup: {e}")
            return False
