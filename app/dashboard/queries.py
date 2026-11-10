"""Everything the dashboard shows, read from the database.

One function per panel, each returning plain dicts and lists that turn
straight into JSON. Reporter phone numbers are never included.

The numbers here are small (a hackathon's worth of cases), so we read the
last 30 days in one go and filter in Python. A real deployment would filter
in SQL and page the list.
"""

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import and_, cast, func, select, true
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app import clock
from app.booking import flow as booking
from app.booking.models import Booking, Camp, SterilisationCount
from app.cases.bites import BiteReport
from app.cases.models import Case, Event, Photo, Report
from app.cases.models import CaseState as S
from app.routing.models import Team, Zone

WINDOW = timedelta(days=30)
STERILISATION_YEAR = 2025
OPEN_STATES = {S.REPORTED, S.TRIAGED, S.NEW, S.ROUTED, S.ESCALATED, S.ACCEPTED, S.ON_SITE}
CLOSED_STATES = {S.RESOLVED, S.CANCELLED}
URGENCY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, None: 4}

SUGGESTION_RULE = (
    "Among municipalities with no camp scheduled, pick the one with the most bite reports "
    "to PawSOS in the last 30 days. A tie goes to one that held no camps in 2025."
)


def _latitude(column):
    return func.ST_Y(cast(column, Geometry))


def _longitude(column):
    return func.ST_X(cast(column, Geometry))


# ---------- zones ----------


def zone_rows(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        select(Zone, _latitude(Zone.centre), _longitude(Zone.centre)).order_by(Zone.short_name)
    )
    return [
        {
            "slug": zone.slug,
            "name": zone.short_name,
            "latitude": lat,
            "longitude": lng,
            "radius_m": zone.radius_m,
            "approximate": zone.approximate,
        }
        for zone, lat, lng in rows
    ]


# ---------- cases ----------


def _attention(case: Case, chain_exhausted: bool) -> str | None:
    """Why a person should look at this case now, if there is a reason."""
    if case.state == S.ESCALATED and chain_exhausted:
        return "no_team"  # every team was asked and nobody took it
    if case.triage_status == "needs_review" and case.state in OPEN_STATES:
        return "needs_review"  # the photo could not be triaged automatically
    return None


def case_sort_key(case: dict[str, Any]) -> Any:
    """The order of the case list: smallest key first.

    TODO(me): Ayush improves this. Right now the list is simply newest first,
    so a critical case from 40 minutes ago sits below a low one from 5
    minutes ago. Make the order:
        1. open cases before closed ones           (case["open"] is True/False)
        2. then the most urgent first              (URGENCY_RANK[case["urgency"]], 0 is critical)
        3. then the one waiting longest first      (case["created_at"], an ISO string; smaller = older)
    Return a tuple: Python compares tuples item by item, so
    (0, 1, "2026-...") sorts before (0, 2, "2026-...").
    Remember False sorts before True, so "open first" needs `not case["open"]`.
    Then remove the @pytest.mark.skip on test_case_list_order in
    tests/test_slice8.py and run:
        .venv/bin/pytest -q tests/test_slice8.py -k list_order
    """
    return -datetime.fromisoformat(case["created_at"]).timestamp()  # newest first


def case_rows(session: Session) -> list[dict[str, Any]]:
    """Every case from the last 30 days, except duplicates that were merged away."""
    report_count = (
        select(func.count())
        .select_from(Report)
        .where(Report.case_id == Case.id)
        .correlate(Case)
        .scalar_subquery()
    )
    chain_exhausted = (
        select(Event.id)
        .where(Event.case_id == Case.id, Event.type == "chain_exhausted")
        .correlate(Case)
        .exists()
    )
    first_photo = (
        select(Photo.path)
        .join(Report, Photo.report_id == Report.id)
        .where(Report.case_id == Case.id)
        .order_by(Photo.id)
        .limit(1)
        .correlate(Case)
        .scalar_subquery()
    )
    rows = session.execute(
        select(
            Case,
            _latitude(Case.location),
            _longitude(Case.location),
            Zone.slug,
            Zone.short_name,
            Team.name,
            report_count,
            chain_exhausted,
            first_photo,
        )
        .outerjoin(Zone, Case.zone_id == Zone.id)
        .outerjoin(Team, Case.assigned_team_id == Team.id)
        .where(Case.state != S.MERGED, Case.created_at >= clock.now() - WINDOW)
    )
    cases = [
        {
            "id": case.public_id,
            "id_number": case.id,
            "state": case.state,
            "open": case.state in OPEN_STATES,
            "species": case.species,
            "injury_type": case.injury_type,
            "urgency": case.urgency,
            "aggression_risk": case.aggression_risk,
            "attention": _attention(case, exhausted),
            "zone": zone_slug,
            "zone_name": zone_name,
            "zone_is_approximate": bool(case.zone_is_approximate),
            "team": team_name,
            "reports": reports,
            "photo_url": f"/media/{photo}" if photo else None,
            "latitude": lat,
            "longitude": lng,
            "created_at": case.created_at.isoformat(),
            "is_demo": case.is_demo,
        }
        for case, lat, lng, zone_slug, zone_name, team_name, reports, exhausted, photo in rows
    ]
    return sorted(cases, key=case_sort_key)


def filter_cases(
    cases: list[dict[str, Any]], status: str, urgency: str | None, zone: str | None
) -> list[dict[str, Any]]:
    wanted_open = {"open": True, "closed": False}.get(status)  # "all" gives None
    return [
        case
        for case in cases
        if (wanted_open is None or case["open"] == wanted_open)
        and (urgency is None or case["urgency"] == urgency)
        and (zone is None or case["zone"] == zone)
    ]


# ---------- bites ----------


def bite_rows(session: Session) -> list[dict[str, Any]]:
    """Located bite reports from the last 30 days, each with its nearest zone."""
    rows = session.execute(
        select(
            BiteReport,
            _latitude(BiteReport.location),
            _longitude(BiteReport.location),
            Zone.slug,
            Zone.short_name,
        )
        .join(Zone, true())  # pair every bite with every zone...
        .where(BiteReport.location.is_not(None), BiteReport.created_at >= clock.now() - WINDOW)
        .ext(distinct_on(BiteReport.id))  # ...and keep only the nearest zone for each bite
        .order_by(BiteReport.id, func.ST_Distance(BiteReport.location, Zone.centre))
    )
    return [
        {
            "latitude": lat,
            "longitude": lng,
            "zone": zone_slug,
            "zone_name": zone_name,
            "is_hotspot": bite.is_hotspot,
            "created_at": bite.created_at.isoformat(),
            "is_demo": bite.is_demo,
        }
        for bite, lat, lng, zone_slug, zone_name in rows
    ]


# ---------- camps and sterilisation ----------


def camp_rows(session: Session) -> list[dict[str, Any]]:
    camps = []
    for camp in booking.upcoming_camps(session):
        lat, lng = session.execute(
            select(_latitude(Camp.location), _longitude(Camp.location)).where(Camp.id == camp.id)
        ).one()
        booked = session.scalar(
            select(func.count())
            .select_from(Booking)
            .where(Booking.camp_id == camp.id, Booking.status == "booked")
        )
        zone = session.get(Zone, camp.zone_id) if camp.zone_id else None
        camps.append(
            {
                "name": camp.name,
                "venue": camp.venue,
                "services": camp.services,
                "zone": zone.slug if zone else None,
                "zone_name": zone.short_name if zone else None,
                "starts_at": camp.slots[0].starts_at.isoformat(),
                "capacity": sum(slot.capacity for slot in camp.slots),
                "booked": booked,
                "latitude": lat,
                "longitude": lng,
            }
        )
    return camps


def sterilisation_rows(session: Session) -> list[dict[str, Any]]:
    """One row per zone. None means we have no figure; it does not mean zero."""
    rows = session.execute(
        select(
            Zone.slug, Zone.short_name, SterilisationCount.camps_held, SterilisationCount.dogs_sterilised
        )
        .outerjoin(
            SterilisationCount,
            and_(
                SterilisationCount.zone_id == Zone.id,
                SterilisationCount.year == STERILISATION_YEAR,
            ),
        )
        .order_by(Zone.short_name)
    )
    return [
        {"zone": slug, "zone_name": name, "camps_held": camps_held, "dogs_sterilised": sterilised}
        for slug, name, camps_held, sterilised in rows
    ]


# ---------- the next-camp suggestion ----------


def suggest_next_camp(
    zones: list[dict[str, Any]],
    bites: list[dict[str, Any]],
    camps: list[dict[str, Any]],
    sterilisation: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """A plain counting rule, not a prediction. See SUGGESTION_RULE."""
    bite_count = Counter(bite["zone"] for bite in bites)
    scheduled = {camp["zone"] for camp in camps}
    no_camps_last_year = {row["zone"] for row in sterilisation if row["camps_held"] == 0}

    def describe(zone: dict[str, Any]) -> dict[str, Any]:
        return {
            "zone": zone["slug"],
            "zone_name": zone["name"],
            "bite_reports": bite_count[zone["slug"]],
            "held_no_camps_last_year": zone["slug"] in no_camps_last_year,
        }

    candidates = [describe(zone) for zone in zones if zone["slug"] not in scheduled]
    if not candidates:
        return None
    ranked = sorted(
        candidates,
        key=lambda c: (-c["bite_reports"], not c["held_no_camps_last_year"], c["zone_name"]),
    )
    return {**ranked[0], "runners_up": ranked[1:3], "rule": SUGGESTION_RULE}


# ---------- everything together ----------


def dashboard_data(
    session: Session, status: str = "all", urgency: str | None = None, zone: str | None = None
) -> dict[str, Any]:
    zones = zone_rows(session)
    all_cases = case_rows(session)
    bites = bite_rows(session)
    camps = camp_rows(session)
    sterilisation = sterilisation_rows(session)
    open_cases = [case for case in all_cases if case["open"]]
    return {
        "generated_at": clock.now().isoformat(),
        "window_days": WINDOW.days,
        "sterilisation_year": STERILISATION_YEAR,
        # The summary always covers everything, whatever the list is filtered to.
        "summary": {
            "open_cases": len(open_cases),
            "critical_open": sum(case["urgency"] == "critical" for case in open_cases),
            "need_attention": sum(case["attention"] is not None for case in all_cases),
            "bite_reports": len(bites),
            "bite_hotspots": sum(bite["is_hotspot"] for bite in bites),
            "demo_cases": sum(case["is_demo"] for case in all_cases),
            "demo_bites": sum(bite["is_demo"] for bite in bites),
        },
        "zones": zones,
        "cases": filter_cases(all_cases, status, urgency, zone),
        "attention": [case for case in all_cases if case["attention"] is not None],
        "bites": bites,
        "camps": camps,
        "sterilisation": sterilisation,
        "suggestion": suggest_next_camp(zones, bites, camps, sterilisation),
    }
