"""Small in-memory sliding-window rate limiter (per process), same as the shop.

Each Passenger worker keeps its own counters, so the effective limit is "per worker" —
enough to slow down password guessing on shared hosting.
"""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, max_hits: int, window_seconds: int):
        self.max_hits = max_hits
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._hits[key]
        while q and q[0] <= now - self.window:
            q.popleft()
        return q

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key, time.monotonic())) >= self.max_hits

    def hit(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now).append(now)
            if len(self._hits) > 10_000:  # keep memory bounded
                for k in [k for k, v in self._hits.items() if not v][:5_000]:
                    del self._hits[k]

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


# Failed sign-ins: 10 per account and 30 per IP address every 15 minutes.
failed_logins_by_email = RateLimiter(max_hits=10, window_seconds=15 * 60)
failed_logins_by_ip = RateLimiter(max_hits=30, window_seconds=15 * 60)
# Password-reset emails: 3 per address and 10 per IP per hour; reset attempts: 20 per IP per 15 min.
reset_requests_by_email = RateLimiter(max_hits=3, window_seconds=60 * 60)
reset_requests_by_ip = RateLimiter(max_hits=10, window_seconds=60 * 60)
reset_attempts_by_ip = RateLimiter(max_hits=20, window_seconds=15 * 60)
# Public unsubscribe links: a stranger's mail client, so keep it to a trickle per IP.
unsubscribe_by_ip = RateLimiter(max_hits=30, window_seconds=15 * 60)
# Campaign tracking (the open pixel and the click redirect): fetched by mail clients, so the limit is
# generous — one mail proxy can ask for the images of a whole batch of messages from one address at once.
tracking_by_ip = RateLimiter(max_hits=600, window_seconds=15 * 60)
