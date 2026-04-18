"""Rate limiting utilities for Toaster 3000."""

import threading
import time


class TokenBucket:
    """Token-bucket rate limiter (no external deps, thread-safe)."""

    def __init__(self, rate: float, capacity: float):
        """
        Args:
            rate: Tokens replenished per second.
            capacity: Maximum burst size (also the starting token count).
        """
        self._rate = rate
        self._capacity = capacity
        self._tokens = capacity
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, tokens: float = 1.0) -> bool:
        """Consume tokens. Returns True if allowed, False if rate-limited."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last = now
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False


class PerSessionCooldown:
    """Enforces a minimum interval between calls (thread-safe)."""

    def __init__(self, min_interval_secs: float):
        self._min = min_interval_secs
        self._last: float = 0.0
        self._lock = threading.Lock()

    def check_and_record(self) -> bool:
        """Return True if enough time has passed; records the call if so."""
        with self._lock:
            now = time.monotonic()
            if now - self._last >= self._min:
                self._last = now
                return True
            return False

    def seconds_remaining(self) -> float:
        """Seconds until the next call is allowed."""
        with self._lock:
            remaining = self._min - (time.monotonic() - self._last)
            return max(0.0, remaining)
