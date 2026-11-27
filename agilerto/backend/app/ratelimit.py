"""A small per-client limit on questions, so one device cannot keep a shared laptop busy. In memory only.
People in danger or distress are never limited (see routes/chat.py)."""
import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window_seconds, clock
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """(allowed, seconds_to_wait). Counts the request when it is allowed."""
        now = self.clock()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] >= self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False, max(1, int(self.window - (now - q[0])) + 1)
            q.append(now)
            if len(self._hits) > 1000:                       # forget clients that went quiet
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window]:
                    self._hits.pop(k, None)
            return True, 0
