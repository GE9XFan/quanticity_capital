"""
Interactive Brokers API Configuration
"""
import os
from dataclasses import dataclass


@dataclass
class IBConfig:
    """Configuration for IB API connection"""

    host: str = "127.0.0.1"
    port: int = 7497  # Paper trading port (7496 for live)
    client_id: int = 0

    @classmethod
    def from_env(cls):
        """Load configuration from environment variables"""
        return cls(
            host=os.getenv("IB_HOST", "127.0.0.1"),
            port=int(os.getenv("IB_PORT", "7497")),
            client_id=int(os.getenv("IB_CLIENT_ID", "0"))
        )
