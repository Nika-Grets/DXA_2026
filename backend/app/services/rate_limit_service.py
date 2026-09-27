import math
import time
from collections import defaultdict, deque
from threading import Lock

from app.core.exceptions import AppError


class AccountRateLimiter:
    """Process-local sliding-window limiter keyed by authenticated user ID."""

    def __init__(self, limit: int, window_seconds: float) -> None:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("Rate limit and window must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._cooldowns: dict[tuple[str, str], float] = {}
        self._lock = Lock()
        self._checks = 0

    def check(self, account_id: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            events = self._events[account_id]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = max(1, math.ceil(events[0] + self.window_seconds - now))
                raise AppError(
                    "RATE_LIMIT_EXCEEDED",
                    "Too many requests for this account",
                    429,
                    details={"limit": self.limit, "window_seconds": self.window_seconds},
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(now)
            self._checks += 1
            if self._checks % 1000 == 0:
                self._remove_idle(cutoff)

    def check_cooldown(self, account_id: str, action_key: str, seconds: float) -> None:
        if seconds <= 0:
            return
        now = time.monotonic()
        key = (account_id, action_key)
        with self._lock:
            ready_at = self._cooldowns.get(key, 0.0)
            if now < ready_at:
                retry_after = max(1, math.ceil(ready_at - now))
                raise AppError(
                    "COOLDOWN_ACTIVE",
                    "This action is temporarily on cooldown",
                    429,
                    details={"action": action_key, "cooldown_seconds": seconds},
                    headers={"Retry-After": str(retry_after)},
                )
            self._cooldowns[key] = now + seconds

    def _remove_idle(self, cutoff: float) -> None:
        idle = [key for key, events in self._events.items() if not events or events[-1] <= cutoff]
        for key in idle:
            self._events.pop(key, None)
        expired = [key for key, ready_at in self._cooldowns.items() if ready_at <= cutoff]
        for key in expired:
            self._cooldowns.pop(key, None)
