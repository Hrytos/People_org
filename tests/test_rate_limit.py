"""Tests for rate limiter."""

import time
import pytest
from src.fullenrich.rate_limit import RateLimiter, get_rate_limiter


class TestRateLimiter:
    """Test RateLimiter token bucket."""

    def test_initial_tokens(self):
        limiter = RateLimiter(requests_per_minute=60)
        assert limiter.get_available_tokens() == 60.0

    def test_acquire_decrements_tokens(self):
        limiter = RateLimiter(requests_per_minute=60)
        limiter.acquire()
        assert limiter.get_available_tokens() == 59.0
        limiter.acquire(2)
        assert limiter.get_available_tokens() == 57.0

    def test_reset_restores_capacity(self):
        limiter = RateLimiter(requests_per_minute=10)
        limiter.acquire(5)
        limiter.reset()
        assert limiter.get_available_tokens() == 10.0

    def test_acquire_non_blocking_returns_false_when_empty(self):
        limiter = RateLimiter(requests_per_minute=2)
        assert limiter.acquire(1, block=False) is True
        assert limiter.acquire(1, block=False) is True
        assert limiter.acquire(1, block=False) is False


class TestGetRateLimiter:
    """Test singleton get_rate_limiter."""

    def test_returns_same_instance(self):
        # Reset global for test isolation (optional; may affect other tests)
        import src.fullenrich.rate_limit as rl
        rl._rate_limiter = None
        a = get_rate_limiter(60)
        b = get_rate_limiter(100)  # param ignored after first call
        assert a is b
