"""
Redis client for storing real-time account and portfolio data
Key structure and TTL defined in docs/3.1 Data Storage Strategy.md
"""
import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, List
import redis
from dotenv import load_dotenv

load_dotenv()


class RedisClient:
    """
    Redis client for account and portfolio data caching

    Key Structure:
    - ib:account:{account}:summary:{tag} - Account summary values
    - ib:account:{account}:positions - Hash of positions
    - ib:account:{account}:pnl - Hash of account PnL
    - ib:account:{account}:position:{contract_id}:pnl - Hash of position PnL
    - ib:account:{account}:last_update:{type} - Last update timestamps
    """

    def __init__(self, host: str = None, port: int = None, password: str = None, db: int = 0):
        """
        Initialize Redis client

        Args:
            host: Redis host (defaults to REDIS_HOST env var or localhost)
            port: Redis port (defaults to REDIS_PORT env var or 6379)
            password: Redis password (defaults to REDIS_PASSWORD env var)
            db: Redis database number (default: 0)
        """
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", "6379"))
        self.password = password or os.getenv("REDIS_PASSWORD", None)
        self.db = db

        self.client = redis.Redis(
            host=self.host,
            port=self.port,
            password=self.password if self.password else None,
            db=self.db,
            decode_responses=True  # Automatically decode bytes to strings
        )

        # Test connection
        try:
            self.client.ping()
            print(f"✓ Redis connected: {self.host}:{self.port}")
        except redis.ConnectionError as e:
            print(f"✗ Redis connection failed: {e}")
            raise

    # ========================================================================
    # Account Summary Methods
    # ========================================================================

    def store_account_summary(self, account: str, tag: str, value: str,
                             currency: str, ttl: int = 180):
        """
        Store account summary value

        Args:
            account: Account identifier
            tag: Summary tag (e.g., "NetLiquidation", "BuyingPower")
            value: Value as string
            currency: Currency code
            ttl: Time-to-live in seconds (default: 180 = 3 minutes)

        Returns:
            bool: True if successful
        """
        value_key = f"ib:account:{account}:summary:{tag}"
        currency_key = f"{value_key}:currency"

        try:
            # Store value and currency
            self.client.setex(value_key, ttl, value)
            self.client.setex(currency_key, ttl, currency)

            # Update last_update timestamp
            self._update_timestamp(account, "summary")

            return True
        except Exception as e:
            print(f"Error storing account summary: {e}")
            return False

    def get_account_summary(self, account: str, tag: str) -> Optional[Dict[str, str]]:
        """
        Get account summary value

        Args:
            account: Account identifier
            tag: Summary tag

        Returns:
            Dict with 'value' and 'currency' keys, or None if not found
        """
        value_key = f"ib:account:{account}:summary:{tag}"
        currency_key = f"{value_key}:currency"

        try:
            value = self.client.get(value_key)
            currency = self.client.get(currency_key)

            if value:
                return {
                    "value": value,
                    "currency": currency or "USD"
                }
            return None
        except Exception as e:
            print(f"Error getting account summary: {e}")
            return None

    def get_all_account_summaries(self, account: str) -> Dict[str, Dict[str, str]]:
        """
        Get all account summary values for an account

        Args:
            account: Account identifier

        Returns:
            Dict of {tag: {"value": value, "currency": currency}}
        """
        pattern = f"ib:account:{account}:summary:*"
        summaries = {}

        try:
            # Get all keys matching pattern (excluding :currency keys)
            keys = [k for k in self.client.keys(pattern) if not k.endswith(":currency")]

            for key in keys:
                # Extract tag from key
                tag = key.split(":")[-1]
                summary = self.get_account_summary(account, tag)
                if summary:
                    summaries[tag] = summary

            return summaries
        except Exception as e:
            print(f"Error getting all account summaries: {e}")
            return {}

    # ========================================================================
    # Position Methods
    # ========================================================================

    def store_position(self, account: str, contract_id: int, position_data: Dict,
                      ttl: int = 300):
        """
        Store position data

        Args:
            account: Account identifier
            contract_id: Contract ID
            position_data: Position data as dict
            ttl: Time-to-live in seconds (default: 300 = 5 minutes)

        Returns:
            bool: True if successful
        """
        key = f"ib:account:{account}:positions"

        try:
            # Convert Decimal values to strings for JSON serialization
            serialized_data = self._serialize_data(position_data)

            # Store as hash field
            self.client.hset(key, str(contract_id), json.dumps(serialized_data))

            # Set TTL on the entire hash
            self.client.expire(key, ttl)

            # Update timestamp
            self._update_timestamp(account, "positions")

            return True
        except Exception as e:
            print(f"Error storing position: {e}")
            return False

    def get_position(self, account: str, contract_id: int) -> Optional[Dict]:
        """
        Get specific position

        Args:
            account: Account identifier
            contract_id: Contract ID

        Returns:
            Position data as dict, or None if not found
        """
        key = f"ib:account:{account}:positions"

        try:
            data = self.client.hget(key, str(contract_id))
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"Error getting position: {e}")
            return None

    def get_all_positions(self, account: str) -> Dict[int, Dict]:
        """
        Get all positions for an account

        Args:
            account: Account identifier

        Returns:
            Dict of {contract_id: position_data}
        """
        key = f"ib:account:{account}:positions"

        try:
            positions = {}
            data = self.client.hgetall(key)

            for contract_id_str, position_json in data.items():
                positions[int(contract_id_str)] = json.loads(position_json)

            return positions
        except Exception as e:
            print(f"Error getting all positions: {e}")
            return {}

    # ========================================================================
    # Account PnL Methods
    # ========================================================================

    def store_account_pnl(self, account: str, daily_pnl: Optional[Decimal],
                         unrealized_pnl: Optional[Decimal],
                         realized_pnl: Optional[Decimal], ttl: int = 60):
        """
        Store account-level P&L

        Args:
            account: Account identifier
            daily_pnl: Daily P&L
            unrealized_pnl: Unrealized P&L
            realized_pnl: Realized P&L
            ttl: Time-to-live in seconds (default: 60)

        Returns:
            bool: True if successful
        """
        key = f"ib:account:{account}:pnl"

        try:
            data = {
                "daily_pnl": str(daily_pnl) if daily_pnl is not None else None,
                "unrealized_pnl": str(unrealized_pnl) if unrealized_pnl is not None else None,
                "realized_pnl": str(realized_pnl) if realized_pnl is not None else None,
                "last_update": datetime.now().isoformat()
            }

            # Remove None values
            data = {k: v for k, v in data.items() if v is not None}

            # Store as hash
            self.client.hset(key, mapping=data)

            # Set TTL
            self.client.expire(key, ttl)

            return True
        except Exception as e:
            print(f"Error storing account PnL: {e}")
            return False

    def get_account_pnl(self, account: str) -> Optional[Dict]:
        """
        Get account-level P&L

        Args:
            account: Account identifier

        Returns:
            Dict with PnL data, or None if not found
        """
        key = f"ib:account:{account}:pnl"

        try:
            data = self.client.hgetall(key)
            if data:
                return data
            return None
        except Exception as e:
            print(f"Error getting account PnL: {e}")
            return None

    # ========================================================================
    # Position PnL Methods
    # ========================================================================

    def store_position_pnl(self, account: str, contract_id: int,
                          position: Optional[Decimal], daily_pnl: Optional[Decimal],
                          unrealized_pnl: Optional[Decimal],
                          realized_pnl: Optional[Decimal],
                          value: Optional[Decimal], ttl: int = 60):
        """
        Store position-level P&L

        Args:
            account: Account identifier
            contract_id: Contract ID
            position: Position size
            daily_pnl: Daily P&L
            unrealized_pnl: Unrealized P&L
            realized_pnl: Realized P&L
            value: Current market value
            ttl: Time-to-live in seconds (default: 60)

        Returns:
            bool: True if successful
        """
        key = f"ib:account:{account}:position:{contract_id}:pnl"

        try:
            data = {
                "position": str(position) if position is not None else None,
                "daily_pnl": str(daily_pnl) if daily_pnl is not None else None,
                "unrealized_pnl": str(unrealized_pnl) if unrealized_pnl is not None else None,
                "realized_pnl": str(realized_pnl) if realized_pnl is not None else None,
                "value": str(value) if value is not None else None
            }

            # Remove None values
            data = {k: v for k, v in data.items() if v is not None}

            # Store as hash
            self.client.hset(key, mapping=data)

            # Set TTL
            self.client.expire(key, ttl)

            return True
        except Exception as e:
            print(f"Error storing position PnL: {e}")
            return False

    def get_position_pnl(self, account: str, contract_id: int) -> Optional[Dict]:
        """
        Get position-level P&L

        Args:
            account: Account identifier
            contract_id: Contract ID

        Returns:
            Dict with PnL data, or None if not found
        """
        key = f"ib:account:{account}:position:{contract_id}:pnl"

        try:
            data = self.client.hgetall(key)
            if data:
                return data
            return None
        except Exception as e:
            print(f"Error getting position PnL: {e}")
            return None

    # ========================================================================
    # Timestamp Methods
    # ========================================================================

    def _update_timestamp(self, account: str, data_type: str):
        """
        Update last update timestamp

        Args:
            account: Account identifier
            data_type: Type of data (e.g., "summary", "positions", "pnl")
        """
        key = f"ib:account:{account}:last_update:{data_type}"
        timestamp = datetime.now().isoformat()

        try:
            self.client.setex(key, 86400, timestamp)  # 24 hour TTL
        except Exception as e:
            print(f"Error updating timestamp: {e}")

    def get_last_update(self, account: str, data_type: str) -> Optional[str]:
        """
        Get last update timestamp

        Args:
            account: Account identifier
            data_type: Type of data

        Returns:
            ISO timestamp string, or None if not found
        """
        key = f"ib:account:{account}:last_update:{data_type}"

        try:
            return self.client.get(key)
        except Exception as e:
            print(f"Error getting last update: {e}")
            return None

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _serialize_data(self, data: Dict) -> Dict:
        """
        Serialize data for JSON storage (convert Decimal to string)

        Args:
            data: Data dict potentially containing Decimal values

        Returns:
            Dict with Decimal values converted to strings
        """
        serialized = {}
        for key, value in data.items():
            if isinstance(value, Decimal):
                serialized[key] = str(value)
            elif isinstance(value, datetime):
                serialized[key] = value.isoformat()
            else:
                serialized[key] = value
        return serialized

    def clear_account_data(self, account: str):
        """
        Clear all data for an account (useful for testing)

        Args:
            account: Account identifier
        """
        pattern = f"ib:account:{account}:*"

        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
                print(f"Cleared {len(keys)} keys for account {account}")
        except Exception as e:
            print(f"Error clearing account data: {e}")

    def ping(self) -> bool:
        """
        Test Redis connection

        Returns:
            bool: True if connected
        """
        try:
            return self.client.ping()
        except Exception as e:
            print(f"Redis ping failed: {e}")
            return False

    def get_stats(self) -> Dict:
        """
        Get Redis stats

        Returns:
            Dict with connection stats
        """
        try:
            info = self.client.info()
            return {
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
                "total_commands_processed": info.get("total_commands_processed"),
                "keyspace_hits": info.get("keyspace_hits"),
                "keyspace_misses": info.get("keyspace_misses")
            }
        except Exception as e:
            print(f"Error getting Redis stats: {e}")
            return {}
