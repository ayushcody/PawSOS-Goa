"""Background jobs.

One job for now: every few seconds, look for team alerts that have gone
unanswered past their deadline and move those cases along. The deadlines live
in the database, so nothing is lost if the server restarts.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.channels.base import ChannelAdapter, deliver
from app.config import get_settings
from app.db import new_session
from app.routing import dispatch

log = logging.getLogger(__name__)


async def run_timeouts(channel: ChannelAdapter) -> None:
    session = new_session()
    try:
        outbox = dispatch.process_timeouts(session)
        session.commit()
    except Exception:
        session.rollback()
        log.exception("Escalation check failed")
        return
    finally:
        session.close()
    await deliver(channel, outbox)


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
    scheduler.start()
    return scheduler
