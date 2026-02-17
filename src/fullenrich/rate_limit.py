"""
Rate Limiter Module

Token bucket rate limiter for FullEnrich API (60 req/min limit).
Following Rulebook: Rate limiting and backoff logic.
"""

import time
import threading
from typing import Optional

from ..core.logging import setup_logger

logger = setup_logger(__name__)

# =============================================================================
# Token Bucket Rate Limiter
# =============================================================================

class RateLimiter:
    """
    Token bucket rate limiter for API requests.
    
    FullEnrich limits: 60 API calls per minute.
    """
    
    def __init__(self, requests_per_minute: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum requests allowed per minute
        """
        self.capacity = requests_per_minute
        self.tokens = requests_per_minute
        self.last_refill = time.time()
        self.lock = threading.Lock()
        
        # Calculate refill rate (tokens per second)
        self.refill_rate = requests_per_minute / 60.0
        
        logger.info(f"Rate limiter initialized: {requests_per_minute} req/min")
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Calculate tokens to add
        tokens_to_add = elapsed * self.refill_rate
        
        if tokens_to_add > 0:
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            self.last_refill = now
    
    def acquire(self, tokens: int = 1, block: bool = True) -> bool:
        """
        Acquire tokens for making requests.
        
        Args:
            tokens: Number of tokens to acquire (default: 1)
            block: If True, wait until tokens are available
            
        Returns:
            True if tokens were acquired, False otherwise
        """
        with self.lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                logger.debug(f"Token acquired. Remaining: {self.tokens:.2f}")
                return True
            
            if not block:
                return False
            
            # Calculate wait time
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.refill_rate
            
            logger.info(f"Rate limit reached. Waiting {wait_time:.2f}s...")
        
        # Wait outside of lock
        time.sleep(wait_time)
        
        # Try again
        return self.acquire(tokens, block=False)
    
    def get_available_tokens(self) -> float:
        """Get number of available tokens."""
        with self.lock:
            self._refill()
            return self.tokens
    
    def reset(self):
        """Reset rate limiter to full capacity."""
        with self.lock:
            self.tokens = self.capacity
            self.last_refill = time.time()
            logger.info("Rate limiter reset")


# =============================================================================
# Global Rate Limiter Instance
# =============================================================================

_rate_limiter: Optional[RateLimiter] = None

def get_rate_limiter(requests_per_minute: int = 60) -> RateLimiter:
    """
    Get global rate limiter instance (singleton).
    
    Args:
        requests_per_minute: Maximum requests per minute
        
    Returns:
        RateLimiter instance
    """
    global _rate_limiter
    
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(requests_per_minute)
    
    return _rate_limiter


# =============================================================================
# Module Test
# =============================================================================

if __name__ == "__main__":
    print("Rate Limiter Test")
    print("=" * 60)
    
    # Test with 10 req/min for quick testing
    limiter = RateLimiter(requests_per_minute=10)
    
    print(f"Initial tokens: {limiter.get_available_tokens():.2f}")
    
    # Make 5 requests quickly
    for i in range(5):
        limiter.acquire()
        print(f"Request {i+1} - Tokens: {limiter.get_available_tokens():.2f}")
    
    print("\nWaiting 3 seconds for refill...")
    time.sleep(3)
    print(f"After 3s - Tokens: {limiter.get_available_tokens():.2f}")
    
    print("✅ Rate limiter test complete")
