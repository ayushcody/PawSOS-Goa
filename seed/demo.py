"""Load invented cases and bite reports so the dashboard has something to show.

    .venv/bin/python -m seed.demo            load (replaces any earlier demo data)
    .venv/bin/python -m seed.demo --clear    remove the demo data again

Only rows marked is_demo are ever touched; real cases are left alone.
Every demo case is walked through the real state machine, so its audit trail
looks like a real one. Run seed.load first: demo cases need the zones.
"""

import json
import math
import sys
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registers every table)
from app import clock
from app.cases import state_machine
from app.cases.audit import log_event
from app.cases.bites import HOTSPOT_MIN_BITES, HOTSPOT_RADIUS_M, BiteReport
from app.cases.geo import point
from app.cases.intake import format_case_id
from app.cases.models import Case, Event, Report
from app.cases.models import CaseState as S
from app.db import get_engine
from app.routing.models import Dispatch, Team, Zone

SEED_DIR = Path(__file__).parent
ACTOR = "demo-seed"
METRES_PER_DEGREE = 111_320  # of latitude; longitude shrinks with cos(latitude)

# The states a case passes through, after REPORTED, to reach each end state.
_HAPPY_PATH = [S.TRIAGED, S.NEW, S.ROUTED, S.ACCEPTED, S.ON_SITE, S.RESOLVED]
PATHS: dict[str, list[S]] = {
    **{state: _HAPPY_PATH[: i + 1] for i, state in enumerate(_HAPPY_PATH)},
    S.ESCALATED: [S.TRIAGED, S.NEW, S.ROUTED, S.ESCALATED],
    S.MERGED: [S.TRIAGED, S.MERGED],
    S.CANCELLED: [S.TRIAGED, S.NEW, S.CANCELLED],
}
HAS_TEAM = {S.ACCEPTED, S.ON_SITE, S.RESOLVED}


def demo_number(n: int) -> str:
    """An invented reporter number. Never a real one."""
    return f"+9100000009{n % 100:02d}"


def _position(centre: dict, north_m: float, east_m: float) -> tuple[float, float]:
    latitude = centre["latitude"] + north_m / METRES_PER_DEGREE
    longitude = centre["longitude"] + east_m / (
        METRES_PER_DEGREE * math.cos(math.radians(centre["latitude"]))
    )
    return round(latitude, 6), round(longitude, 6)


def clear_demo(session: Session) -> None:
    demo_cases = select(Case.id).where(Case.is_demo)
    for table in (Event, Report, Dispatch):
        session.execute(
            delete(table).where(table.case_id.in_(demo_cases)).execution_options(synchronize_session=False)
        )
    session.execute(
        update(Case).where(Case.is_demo).values(merged_into_id=None).execution_options(synchronize_session=False)
    )
    session.execute(delete(Case).where(Case.is_demo).execution_options(synchronize_session=False))
    session.execute(
        delete(BiteReport).where(BiteReport.is_demo).execution_options(synchronize_session=False)
    )
    session.expire_all()


def load_demo(session: Session) -> dict[str, int]:
    data = json.loads((SEED_DIR / "demo_cases.json").read_text(encoding="utf-8"))
    centres = {
        row["slug"]: row
        for row in json.loads((SEED_DIR / "zones.json").read_text(encoding="utf-8"))["zones"]
    }
    zones = {zone.slug: zone for zone in session.scalars(select(Zone))}
    if not zones:
        raise RuntimeError("No zones in the database. Run:  .venv/bin/python -m seed.load")
    partner = {
        team.zone_id: team for team in session.scalars(select(Team).where(Team.kind == "partner"))
    }

    clear_demo(session)
    now = clock.now()
    made: list[Case] = []

    for n, row in enumerate(data["cases"], start=1):
        zone = zones[row["zone"]]
        latitude, longitude = _position(centres[row["zone"]], row["north_m"], row["east_m"])
        created = now - timedelta(hours=row["hours_ago"])
        needs_review = row.get("needs_review", False)

        case = Case(
            state=S.REPORTED,
            location=point(latitude, longitude),
            is_demo=True,
            created_at=created,
            # When triage fails the real flow leaves the animal blank and assumes "high".
            species=None if needs_review else row["species"],
            injury_type=None if needs_review else row["injury"],
            urgency="high" if needs_review else row["urgency"],
            aggression_risk=None if needs_review else row["aggression"],
            triage_status="needs_review" if needs_review else "ok",
            triaged_at=created + timedelta(minutes=1),
        )
        session.add(case)
        session.flush()
        case.public_id = format_case_id(case.id)
        report = Report(
            case_id=case.id,
            reporter_number=demo_number(n),
            location=point(latitude, longitude),
            created_at=created,
        )
        session.add(report)
        log_event(
            session, "case_created", case_id=case.id, actor=ACTOR,
            to_state=S.REPORTED, data={"demo": True},
        )

        target = S(row["state"])
        if target == S.MERGED:
            primary = made[row["duplicate_of"] - 1]
            case.merged_into_id = primary.id
            report.case_id = primary.id  # as in a real merge, the report moves over
        else:
            case.zone_id = zone.id
            case.zone_is_approximate = False
        if target in HAS_TEAM:
            case.assigned_team_id = partner[zone.id].id

        for state in PATHS[target]:
            state_machine.transition(session, case, state, actor=ACTOR, data={"demo": True})
        if row.get("no_team"):
            log_event(session, "chain_exhausted", case_id=case.id, actor=ACTOR, data={"demo": True})

        # Spread the audit trail over the minutes after the report, never into the future.
        session.flush()
        events = session.scalars(select(Event).where(Event.case_id == case.id).order_by(Event.id))
        for step, event in enumerate(events):
            event.created_at = min(created + timedelta(minutes=2 * step), now)
        made.append(case)

    bites: list[BiteReport] = []
    for n, row in enumerate(data["bites"], start=1):
        latitude, longitude = _position(centres[row["zone"]], row["north_m"], row["east_m"])
        bite = BiteReport(
            reporter_number=demo_number(50 + n),
            location=point(latitude, longitude),
            is_demo=True,
            created_at=now - timedelta(days=row["days_ago"]),
        )
        session.add(bite)
        bites.append(bite)
    session.flush()

    # The same hotspot rule as the live bite flow: enough bites close together.
    for bite in bites:
        here = select(BiteReport.location).where(BiteReport.id == bite.id).scalar_subquery()
        nearby = session.scalar(
            select(func.count())
            .select_from(BiteReport)
            .where(
                BiteReport.location.is_not(None),
                func.ST_DWithin(BiteReport.location, here, HOTSPOT_RADIUS_M),
            )
        )
        bite.is_hotspot = nearby >= HOTSPOT_MIN_BITES
    session.flush()
    return {"cases": len(made), "bites": len(bites)}


if __name__ == "__main__":
    with Session(get_engine()) as session:
        if "--clear" in sys.argv:
            clear_demo(session)
            session.commit()
            print("Demo cases and bite reports removed.")
        else:
            counts = load_demo(session)
            session.commit()
            print(f"Loaded {counts['cases']} demo cases and {counts['bites']} demo bite reports.")
