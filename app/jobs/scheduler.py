"""Background jobs.

Two jobs. Every few seconds: look for team alerts that have gone unanswered
past their deadline and move those cases along. Every five minutes (by default): send
day-before reminders for camp bookings. Deadlines and bookings live in the
database, so nothing is lost if the server restarts.
"""

import logging
from collections.abc import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from app.booking import flow as booking
from app.channels.base import ChannelAdapter, Outbound, deliver
from app.config import get_settings
from app.db import new_session
from app.routing import dispatch

log = logging.getLogger(__name__)


async def _run(name: str, work: Callable[[Session], list[Outbound]], channel: ChannelAdapter) -> None:
    """Do one job's database work, save it, then send what it produced."""
    session = new_session()
    try:
        outbox = work(session)
        session.commit()
    except Exception:
        session.rollback()
        log.exception("%s failed", name)
        return
    finally:
        session.close()
    await deliver(channel, outbox)


async def run_timeouts(channel: ChannelAdapter) -> None:
    await _run("Escalation check", dispatch.process_timeouts, channel)


async def run_reminders(channel: ChannelAdapter) -> None:
    await _run("Reminder check", booking.due_reminders, channel)


def check_interval_seconds(timeout_seconds: int) -> int:
    """Check often enough that a deadline is never missed by more than a tenth of itself."""
    return max(1, min(15, timeout_seconds // 10))


def start(channel: ChannelAdapter) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_timeouts,
        "interval",
        seconds=check_interval_seconds(get_settings().escalation_timeout_seconds),
        args=[channel],
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_reminders,
        "interval",
        seconds=max(5, get_settings().reminder_check_seconds),
        args=[channel],
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    return scheduler
