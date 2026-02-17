"""
Core module - Configuration, logging, and shared utilities.
"""

from .config import (
    FULLENRICH_API_KEY,
    FULLENRICH_BASE_URL,
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY,
    RATE_LIMIT_PER_MINUTE,
    BATCH_SIZE,
    validate_config
)

from .logging import setup_logger, logger
from .http import HTTPClient

__all__ = [
    "FULLENRICH_API_KEY",
    "FULLENRICH_BASE_URL",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "RATE_LIMIT_PER_MINUTE",
    "BATCH_SIZE",
    "validate_config",
    "setup_logger",
    "logger",
    "HTTPClient"
]
