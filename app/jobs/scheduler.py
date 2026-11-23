"""Background jobs.

Four jobs. Every few seconds: look for team alerts that have gone unanswered
past their deadline and move those cases along. Every five minutes (by default): send
day-before reminders for camp bookings. Every 30 seconds: move on any case that
stalled before a team was alerted (app/cases/recovery.py). Every hour: delete
public-demo sandbox cases past SANDBOX_TTL_HOURS (app/sandbox/core.py). Deadlines, bookings
and cases live in the database, so nothing is lost if the server restarts.
"""

import logging
from collections.abc import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from app.booking import flow as booking
from app.cases import recovery
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


async def run_recovery(channel: ChannelAdapter) -> None:
    await _run("Stuck case check", recovery.recover_stuck_cases, channel)


async def run_sandbox_cleanup(simulator=None) -> None:
    """Delete public-demo sandbox cases past their time, and forget old simulator chats."""
    from datetime import UTC, datetime, timedelta

    from app.sandbox import core as sandbox

    session = new_session()
    try:
        deleted = sandbox.cleanup(session)
        session.commit()
        if deleted:
            log.info("Sandbox cleanup deleted %d cases", deleted)
    except Exception:
        session.rollback()
        log.exception("Sandbox cleanup failed")
    finally:
        session.close()
    if simulator is not None:
        hours = get_settings().sandbox_ttl_hours
        simulator.prune(datetime.now(UTC) - timedelta(hours=hours))


RECOVERY_CHECK_SECONDS = 30
SANDBOX_CLEANUP_SECONDS = 3600


def check_interval_seconds(timeout_seconds: int) -> int:
    """Check often enough that a deadline is never missed by more than a tenth of itself."""
    return max(1, min(15, timeout_seconds // 10))


def start(channel: ChannelAdapter, simulator=None) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_sandbox_cleanup,
        "interval",
        seconds=SANDBOX_CLEANUP_SECONDS,
        args=[simulator],
        max_instances=1,
        coalesce=True,
    )
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
    scheduler.add_job(
        run_recovery,
        "interval",
        seconds=RECOVERY_CHECK_SECONDS,
        args=[channel],
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    return scheduler
