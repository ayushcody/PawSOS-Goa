"""Start a rehearsal from a known state.

    .venv/bin/python -m seed.reset          shows what would be deleted, deletes nothing
    .venv/bin/python -m seed.reset --yes    deletes it, then reloads seed and demo data

THIS DELETES DATA: every case, report, photo record, team alert, audit event,
bite report and booking, real ones included. Zones, teams, health centres and
camps are kept. Case numbers start again from PAW-0001.

Why it exists: a rehearsal leaves an open case behind, and the next rehearsal's
report from the same spot would be merged into it instead of opening a new
case. Restart the server afterwards, so the simulator's chats are empty too.
"""

import sys

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registers every table)
from app.booking.models import Booking, BookingDraft
from app.cases.bites import BiteReport
from app.cases.models import Case, Event, Photo, Report
from app.contacts import Contact
from app.db import get_engine
from app.routing.models import Dispatch
from seed.demo import load_demo
from seed.load import load_seed

# Everything that records something that happened. Reference data is not listed.
ACTIVITY_TABLES = [Dispatch, Event, Photo, Report, Case, BiteReport, Booking, BookingDraft, Contact]


def activity_counts(session: Session) -> dict[str, int]:
    return {
        table.__tablename__: session.scalar(select(func.count()).select_from(table))
        for table in ACTIVITY_TABLES
    }


def reset(session: Session) -> dict[str, int]:
    """Empty the activity tables, then load seed and demo data again."""
    names = ", ".join(table.__tablename__ for table in ACTIVITY_TABLES)
    session.execute(text(f"TRUNCATE {names} RESTART IDENTITY"))
    session.expire_all()
    load_seed(session)
    return load_demo(session)


if __name__ == "__main__":
    with Session(get_engine()) as session:
        counts = activity_counts(session)
        real_cases = session.scalar(
            select(func.count()).select_from(Case).where(Case.is_demo.is_(False))
        )
        print("Rows that a reset deletes:")
        for name, count in counts.items():
            print(f"  {name:16} {count}")
        print(f"Of the cases, {real_cases} are real (not demo data).")

        if "--yes" not in sys.argv:
            print("\nNothing was deleted. To go ahead, run:  .venv/bin/python -m seed.reset --yes")
            sys.exit(0)

        loaded = reset(session)
        session.commit()
        print(
            f"\nDone. Loaded {loaded['cases']} demo cases and {loaded['bites']} demo bite reports. "
            "Now restart the server."
        )
