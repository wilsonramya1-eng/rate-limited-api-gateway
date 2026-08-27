from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass(frozen=True)
class Decision:
    allowed: bool
    limit: int
    remaining: int
    retry_after: float = 0.0


class RateLimiter(Protocol):
    def check(self, key: str, now: float | None = None) -> Decision: ...


class TokenBucket:
    """Thread-safe token bucket with continuous refill."""

    def __init__(self, capacity: int, refill_per_second: float) -> None:
        if capacity <= 0 or refill_per_second <= 0:
            raise ValueError("capacity and refill_per_second must be positive")
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self._state: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> Decision:
        timestamp = time.monotonic() if now is None else now
        with self._lock:
            tokens, updated = self._state.get(key, (float(self.capacity), timestamp))
            tokens = min(self.capacity, tokens + max(0.0, timestamp - updated) * self.refill_per_second)
            if tokens >= 1:
                tokens -= 1
                self._state[key] = (tokens, timestamp)
                return Decision(True, self.capacity, int(tokens))
            retry = (1 - tokens) / self.refill_per_second
            self._state[key] = (tokens, timestamp)
            return Decision(False, self.capacity, 0, retry)


class SlidingWindow:
    """Exact sliding-window limiter suitable for a single gateway process."""

    def __init__(self, limit: int, window_seconds: float) -> None:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("limit and window_seconds must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> Decision:
        timestamp = time.monotonic() if now is None else now
        cutoff = timestamp - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) < self.limit:
                events.append(timestamp)
                return Decision(True, self.limit, self.limit - len(events))
            return Decision(False, self.limit, 0, max(0.0, events[0] + self.window_seconds - timestamp))


def client_key(headers: dict[str, str], client_host: str | None) -> str:
    """Prefer an API key; otherwise use the first trusted forwarded address or peer IP."""
    if api_key := headers.get("x-api-key"):
        return f"api:{api_key}"
    if forwarded := headers.get("x-forwarded-for"):
        return f"ip:{forwarded.split(',')[0].strip()}"
    return f"ip:{client_host or 'unknown'}"

