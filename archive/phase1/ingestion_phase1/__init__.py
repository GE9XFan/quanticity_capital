"""Unusual Whales ingestion service package."""

from .config import IngestionSettings
from .service import IngestionService

__all__ = ["IngestionSettings", "IngestionService"]
