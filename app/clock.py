"""The current time, in one place.

Code that depends on the time (opening hours, escalation timers) calls
clock.now() instead of datetime.now(), so tests can set the time.
"""

from datetime import UTC, datetime


def now() -> datetime:
    return datetime.now(UTC)
