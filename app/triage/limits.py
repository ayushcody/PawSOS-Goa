"""Limits for the public demo, so strangers cannot run up the model bill or flood the server.

Kept in memory: a restart resets the counts, which is acceptable for one demo server.
Over the limit, triage is simply skipped: the case goes on through the existing
"a team member will look at your photo" path, as when the model is unavailable.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from app.config import get_settings

HOUR = 3600.0
DAY = 86400.0
MINUTE = 60.0


class SlidingWindow:
    """At most `limit` events per `seconds`, per key."""

    def __init__(self, clock=time.monotonic) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._clock = clock

    def _trim(self, key: str, seconds: float, now: float) -> deque[float]:
        events = self._events[key]
        while events and now - events[0] >= seconds:
            events.popleft()
        return events

    def allow(self, key: str, limit: int, seconds: float) -> bool:
        return self.allow_all([(key, limit, seconds)])

    def allow_all(self, rules: list[tuple[str, int, float]]) -> bool:
        """Record one event under every key, but only if every key still has room."""
        now = self._clock()
        with self._lock:
            windows = [self._trim(key, seconds, now) for key, _, seconds in rules]
            if any(len(w) >= limit for w, (_, limit, _) in zip(windows, rules, strict=True)):
                return False
            for w in windows:
                w.append(now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


_triage = SlidingWindow()
_requests = SlidingWindow()


def allow_triage(sandbox_key: str) -> bool:
    """Spend one real triage call for this sandbox, if both its hourly and the global daily budget allow."""
    settings = get_settings()
    return _triage.allow_all([
        ("all", settings.triage_daily_cap, DAY),
        (f"sandbox:{sandbox_key}", settings.sandbox_triage_per_hour, HOUR),
    ])


class CappedTriager:
    """Wraps a triager so each real call spends one unit of a sandbox's budget.

    Over budget, it raises TriageUnavailable: triage_case then routes the case
    without triage, exactly as when the model is down.
    """

    def __init__(self, inner, sandbox_key: str) -> None:
        self._inner = inner
        self._key = sandbox_key

    async def triage(self, image: bytes, language: str = "en"):
        from app.triage.service import TriageUnavailable

        if not allow_triage(self._key):
            raise TriageUnavailable("public demo limit reached")
        if language == "en":
            return await self._inner.triage(image)
        return await self._inner.triage(image, language=language)


def capped(triager, sandbox_key: str):
    return None if triager is None else CappedTriager(triager, sandbox_key)


READS_PER_WRITE = 8  # a page polling every 2 s makes about 90 reads a minute


def allow_request(client: str, reading: bool = False) -> bool:
    limit = get_settings().sandbox_requests_per_minute
    if reading:
        return _requests.allow(f"read:{client}", limit * READS_PER_WRITE, MINUTE)
    return _requests.allow(f"write:{client}", limit, MINUTE)


def reset() -> None:
    """For tests."""
    _triage.clear()
    _requests.clear()
