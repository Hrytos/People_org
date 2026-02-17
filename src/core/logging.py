"""
Logging Module

Structured logging with PII redaction following the Rulebook.
"""

import logging
import re
from typing import Any

# =============================================================================
# PII Redaction Patterns
# =============================================================================

EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
PHONE_PATTERN = re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b')

# =============================================================================
# Custom Formatter with Redaction
# =============================================================================

class RedactedFormatter(logging.Formatter):
    """Custom formatter that redacts PII from log messages."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with PII redaction."""
        original = super().format(record)
        
        # Redact emails
        redacted = EMAIL_PATTERN.sub('***@***.***', original)
        
        # Redact phone numbers
        redacted = PHONE_PATTERN.sub('***-***-****', redacted)
        
        return redacted


# =============================================================================
# Logger Setup
# =============================================================================

def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Setup a logger with PII redaction.
    
    Args:
        name: Logger name (usually __name__)
        level: Logging level
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler
    handler = logging.StreamHandler()
    handler.setLevel(level)
    
    # Use redacted formatter
    formatter = RedactedFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    
    return logger


# =============================================================================
# Default Logger
# =============================================================================

logger = setup_logger(__name__)


# =============================================================================
# Module Test
# =============================================================================

if __name__ == "__main__":
    test_logger = setup_logger("test", logging.DEBUG)
    
    test_logger.info("Testing logger...")
    test_logger.info("Email: john.doe@example.com")
    test_logger.info("Phone: 555-123-4567")
    test_logger.info("Should be redacted above")
