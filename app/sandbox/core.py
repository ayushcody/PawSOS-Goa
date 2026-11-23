"""Private sandboxes for the public demo on the website.

Each visitor gets a sandbox: a random id kept in a signed cookie, and two invented
citizen numbers built from it. The numbers start +91 0, which no Indian mobile does,
so they can never reach a real person.

Isolation rests on three rules:
- dedup only merges reports from the same sandbox (app/routing/dedup.py),
- a team's chat, seen from a sandbox, shows only messages about that sandbox's cases,
- a team button pressed from a sandbox must be for one of that sandbox's cases.
"""

import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.booking.models import Booking, BookingDraft
from app.cases.aftercare import Rating, RescuePhoto
from app.cases.bites import BiteReport
from app.cases.models import Case, Event, Photo, Report
from app.config import get_settings
from app.contacts import Contact
from app.routing.models import Dispatch
from app.sandbox.numbers import CITIZENS, ID_DIGITS, PREFIX, key_for, key_of, new_id, number_for

__all__ = ["CITIZENS", "PREFIX", "key_for", "key_of", "new_id", "number_for"]

CASE_ID = re.compile(r"PAW-\d{4,}")


# ---------- the visitor's cookie ----------


@lru_cache
def _secret() -> bytes:
    configured = get_settings().sandbox_secret
    return configured.encode() if configured else secrets.token_bytes(32)


def sign(sandbox_id: str) -> str:
    mac = hmac.new(_secret(), sandbox_id.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{sandbox_id}.{mac}"


def verify(cookie: str | None) -> str | None:
    """The sandbox id from a cookie we signed, or None."""
    if not cookie or "." not in cookie:
        return None
    sandbox_id, mac = cookie.split(".", 1)
    if len(sandbox_id) != ID_DIGITS or not sandbox_id.isdigit():
        return None
    expected = sign(sandbox_id).split(".", 1)[1]
    return sandbox_id if hmac.compare_digest(mac, expected) else None


# ---------- which cases belong to a sandbox ----------


def _reported_from(key: str):
    """Ids of cases that hold a report from this sandbox's numbers."""
    return select(Report.case_id).where(
        Report.case_id.is_not(None), Report.reporter_number.like(f"{key}%")
    )


def case_ids(session: Session, key: str) -> set[str]:
    """Public ids of this sandbox's cases, including cases merged into them."""
    ids = select(Case.id).where(Case.id.in_(_reported_from(key)))
    rows = session.scalars(
        select(Case.public_id).where(or_(Case.id.in_(ids), Case.merged_into_id.in_(ids)))
    )
    return set(rows)


def owns_case(session: Session, key: str, public_id: str) -> bool:
    return public_id in case_ids(session, key)


def mentioned_cases(text: str, buttons: list[dict[str, str]]) -> set[str]:
    found = set(CASE_ID.findall(text))
    for button in buttons:
        found.update(CASE_ID.findall(button.get("id", "")))
    return found


# ---------- cleanup ----------


def cleanup(session: Session, now: datetime | None = None) -> int:
    """Delete sandbox activity older than SANDBOX_TTL_HOURS. Returns the number of cases deleted.

    Only rows tied to sandbox numbers are touched: real and demo cases are never deleted here.
    """
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(hours=get_settings().sandbox_ttl_hours)
    sandbox_number = Report.reporter_number.like(f"{PREFIX}%")

    primaries = select(Report.case_id).where(sandbox_number, Report.case_id.is_not(None))
    old = select(Case.id).where(Case.id.in_(primaries), Case.created_at < cutoff)
    case_rows = select(Case.id).where(or_(Case.id.in_(old), Case.merged_into_id.in_(old)))
    doomed = list(session.scalars(case_rows))

    if doomed:
        report_ids = select(Report.id).where(Report.case_id.in_(doomed))
        session.execute(delete(Photo).where(Photo.report_id.in_(report_ids)))
        for table in (Dispatch, Event, RescuePhoto, Rating):
            session.execute(delete(table).where(table.case_id.in_(doomed)))
        session.execute(delete(Report).where(Report.case_id.in_(doomed)))
        # Merged cases point at their primary: clear the links before deleting.
        session.execute(
            Case.__table__.update().where(Case.id.in_(doomed)).values(merged_into_id=None)
        )
        session.execute(delete(Case).where(Case.id.in_(doomed)))

    # Drafts never turned into a case, and the rest of a sandbox's footprint.
    stale_drafts = select(Report.id).where(
        sandbox_number, Report.case_id.is_(None), Report.created_at < cutoff
    )
    session.execute(delete(Photo).where(Photo.report_id.in_(stale_drafts)))
    session.execute(
        delete(Report).where(sandbox_number, Report.case_id.is_(None), Report.created_at < cutoff)
    )
    session.execute(
        delete(BiteReport).where(
            BiteReport.reporter_number.like(f"{PREFIX}%"), BiteReport.created_at < cutoff
        )
    )
    session.execute(
        delete(Booking).where(Booking.owner_number.like(f"{PREFIX}%"), Booking.created_at < cutoff)
    )
    session.execute(
        delete(BookingDraft).where(
            BookingDraft.owner_number.like(f"{PREFIX}%"), BookingDraft.updated_at < cutoff
        )
    )
    session.execute(
        delete(Contact).where(Contact.number.like(f"{PREFIX}%"), Contact.updated_at < cutoff)
    )
    return len(doomed)


def count_cases(session: Session) -> int:
    """How many sandbox cases exist now (for logs and tests)."""
    primaries = select(Report.case_id).where(Report.reporter_number.like(f"{PREFIX}%"))
    return session.scalar(select(func.count()).select_from(Case).where(Case.id.in_(primaries)))
