"""Everything the dashboard shows, read from the database.

One function per panel, each returning plain dicts and lists that turn
straight into JSON. Reporter phone numbers are never included.

The numbers here are small (a hackathon's worth of cases), so we read the
last 30 days in one go and filter in Python. A real deployment would filter
in SQL and page the list.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from statistics import median
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import and_, cast, func, or_, select, true
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app import clock
from app.booking import flow as booking
from app.booking.models import Booking, Camp, SterilisationCount
from app.cases.bites import BiteReport
from app.cases.models import Case, Event, Photo, Report
from app.cases.models import CaseState as S
from app.cases.state_machine import can_transition
from app.routing.dispatch import STAFF_CAN_ASSIGN
from app.routing.models import Dispatch, Team, Zone
from app.routing.teams import escalation_chain

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


def photo_url(photo_id: int) -> str:
    """Photos are fetched by their id, behind the staff password (see routes.py)."""
    return f"/dashboard/photos/{photo_id}"


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
        select(Photo.id)
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
            "photo_url": photo_url(photo) if photo else None,
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


# ---------- response times ----------

RESPONSE_TIME_RULE = (
    "Measured from the audit log: report is when the case was opened, accepted is the first "
    "move to Accepted, resolved the first move to Resolved. Only cases that reached a step "
    "are counted for it, so cases still waiting are not included."
)


def _percentile(ordered: list[float], fraction: float) -> float:
    """Linear interpolation between the closest ranks (the usual spreadsheet method)."""
    position = (len(ordered) - 1) * fraction
    below = int(position)
    above = min(below + 1, len(ordered) - 1)
    return ordered[below] + (ordered[above] - ordered[below]) * (position - below)


def _spread(seconds: list[float]) -> dict[str, Any]:
    if not seconds:
        return {"cases": 0, "median_seconds": None, "p90_seconds": None}
    ordered = sorted(seconds)
    return {
        "cases": len(ordered),
        "median_seconds": round(median(ordered)),
        "p90_seconds": round(_percentile(ordered, 0.9)),
    }


def response_times(session: Session) -> dict[str, Any]:
    """Median and 90th percentile, report to accepted and accepted to resolved.

    Covers the same cases as the list (last 30 days, merged duplicates left
    out), overall and per zone. Every figure comes from the events table.
    """

    def first(event_type: str, to_state: str | None = None):
        conditions = [Event.case_id == Case.id, Event.type == event_type]
        if to_state is not None:
            conditions.append(Event.to_state == to_state)
        return select(func.min(Event.created_at)).where(*conditions).correlate(Case).scalar_subquery()

    rows = session.execute(
        select(
            Case.created_at,
            first("case_created"),
            first("state_changed", S.ACCEPTED),
            first("state_changed", S.RESOLVED),
            Zone.slug,
            Zone.short_name,
        )
        .outerjoin(Zone, Case.zone_id == Zone.id)
        .where(Case.state != S.MERGED, Case.created_at >= clock.now() - WINDOW)
    )

    to_accept: dict[str | None, list[float]] = defaultdict(list)
    to_resolve: dict[str | None, list[float]] = defaultdict(list)
    names: dict[str, str] = {}
    for created_at, reported_at, accepted_at, resolved_at, slug, name in rows:
        if slug is not None:
            names[slug] = name
        reported_at = reported_at or created_at
        if accepted_at is not None and accepted_at >= reported_at:
            to_accept[slug].append((accepted_at - reported_at).total_seconds())
            if resolved_at is not None and resolved_at >= accepted_at:
                to_resolve[slug].append((resolved_at - accepted_at).total_seconds())

    def everything(by_zone: dict[str | None, list[float]]) -> list[float]:
        return [value for values in by_zone.values() for value in values]

    zones = sorted(slug for slug in set(to_accept) | set(to_resolve) if slug is not None)
    return {
        "rule": RESPONSE_TIME_RULE,
        "overall": {
            "report_to_accept": _spread(everything(to_accept)),
            "accept_to_resolve": _spread(everything(to_resolve)),
        },
        "zones": sorted(
            (
                {
                    "zone": slug,
                    "zone_name": names[slug],
                    "report_to_accept": _spread(to_accept[slug]),
                    "accept_to_resolve": _spread(to_resolve[slug]),
                }
                for slug in zones
            ),
            key=lambda row: row["zone_name"],
        ),
    }


# ---------- one case in detail ----------

STATE_WORDS = {
    S.REPORTED: "Reported", S.TRIAGED: "Triaged", S.MERGED: "Merged into another case",
    S.NEW: "New", S.ROUTED: "Team alerted", S.ESCALATED: "Escalated", S.ACCEPTED: "Accepted",
    S.ON_SITE: "Team on site", S.RESOLVED: "Resolved", S.CANCELLED: "Cancelled",
}
EVENT_WORDS = {
    "photo_received": "Photo received",
    "location_received": "Location received",
    "voice_note_received": "Description received (voice note)",
    "description_typed": "Description received (typed)",
    "case_created": "Case opened",
    "zone_assigned": "Placed in an area",
    "urgency_raised": "Urgency raised by a second report",
    "report_merged_in": "Another report of the same animal was added",
    "team_alerted": "Team alerted",
    "team_skipped_closed": "Team skipped: closed at this hour",
    "team_declined": "Team declined",
    "alert_timed_out": "Team did not answer in time",
    "chain_exhausted": "Every team in the chain was asked; none has taken it",
    "team_assigned_by_staff": "Staff sent the case to a team",
}
# Events written before the case existed carry the report's id instead of the case's.
INTAKE_EVENTS = (
    "photo_received", "location_received", "voice_note_received", "description_typed"
)
ACTOR_WORDS = {
    "routing": "PawSOS (routing)",
    "triage": "PawSOS (photo check)",
    "timer": "PawSOS (timer)",
    "staff": "Staff",
    "demo-seed": "Demo data",
}
REASON_WORDS = {
    "chain_exhausted": "no team left to ask",
    "ok": "assessed automatically",
    "no_triager": "automatic photo check is switched off",
    "photo_missing": "the photo could not be found",
    "no_animal_visible": "no animal could be seen clearly in the photo",
    "unexpected_error": "the photo check failed unexpectedly",
}
DISPATCH_WORDS = {
    "sent": "Alert sent, waiting for an answer",
    "accepted": "Accepted",
    "declined": "Declined",
    "timed_out": "Did not answer in time",
    "skipped_closed": "Skipped: closed at that hour",
    "cancelled": "Stood down",
}


def _reason_words(reason: str) -> str:
    if reason.startswith("unavailable"):
        return "the photo check service did not answer"
    return REASON_WORDS.get(reason, reason)


def _event_details(event: Event) -> str:
    """A short plain-language line from an event's data. Never includes a phone number."""
    data = event.data or {}
    parts: list[str] = []
    if event.type == "zone_assigned":
        where = f"{data.get('zone')}, {data.get('distance_m')} m from its centre"
        parts.append(where if data.get("within_radius", True) else where + ", outside its usual area")
    elif event.type == "urgency_raised":
        parts.append(f"{data.get('from') or 'unknown'} to {data.get('to')}, because of {data.get('because_of')}")
    elif event.type == "report_merged_in":
        parts.append(f"from {data.get('from_case')}")
    elif event.type == "case_created" and "photos" in data:
        parts.append(f"{data['photos']} photo(s)")
    else:
        if data.get("team"):
            parts.append(f"team: {data['team']}")
        if data.get("to_team"):
            parts.append(f"now alerting {data['to_team']}")
        if data.get("triage_status"):
            parts.append(
                "photo assessed" if data["triage_status"] == "ok" else "needs a person to review"
            )
        if data.get("urgency"):
            parts.append(f"urgency {data['urgency']}")
        if data.get("reason"):
            parts.append(f"reason: {_reason_words(str(data['reason']))}")
        if data.get("merged_into"):
            parts.append(f"merged into {data['merged_into']}")
        if data.get("language"):
            parts.append(f"language: {data['language']}")
    if data.get("demo"):
        parts.append("demo data")
    return "; ".join(parts)


def _actor_words(actor: str | None, teams: dict[str, str], reporters: dict[str, str]) -> str:
    """Who did it, without ever showing a phone number."""
    if actor is None:
        return "PawSOS"
    if actor in teams:
        return teams[actor]
    if actor in reporters:
        return reporters[actor]
    if actor in ACTOR_WORDS:
        return ACTOR_WORDS[actor]
    if actor.lstrip("+").isdigit():
        return "A reporter"  # a number we cannot match: still never shown
    return actor


def find_case(session: Session, public_id: str, *, lock: bool = False) -> Case | None:
    query = select(Case).where(Case.public_id == public_id)
    if lock:
        query = query.with_for_update()  # staff actions wait for a team's button tap, and vice versa
    return session.scalar(query)


def team_choices(session: Session, case: Case) -> list[dict[str, Any]]:
    """Every team, the case's own escalation chain first, then the rest nearest first."""
    zone = session.get(Zone, case.zone_id) if case.zone_id else None
    chain = escalation_chain(session, zone) if zone else []
    here = select(Case.location).where(Case.id == case.id).scalar_subquery()
    rows = session.execute(
        select(Team, Zone.short_name, func.ST_Distance(Zone.centre, here))
        .outerjoin(Zone, Team.zone_id == Zone.id)
        .order_by(func.ST_Distance(Zone.centre, here).nulls_last(), Team.name)
    )
    found = {team.id: (team, zone_name, metres) for team, zone_name, metres in rows}

    def describe(team: Team, zone_name: str | None, metres: float | None, role: str | None):
        return {
            "id": team.id,
            "name": team.name,
            "kind": team.kind,
            "zone_name": zone_name or team.taluka,
            "distance_km": round(metres / 1000, 1) if metres is not None else None,
            "suggested": role is not None,
            "role": role,
        }

    choices = []
    for team in chain:
        if team.kind == "taluka_officer":
            role = f"Taluka officer ({team.taluka})"
        elif team.zone_id == case.zone_id:
            role = "This area's team"
        else:
            role = "Nearest neighbouring area's team"
        _, zone_name, metres = found.get(team.id, (team, None, None))
        choices.append(describe(team, zone_name, metres, role))
    in_chain = {team.id for team in chain}
    choices += [
        describe(team, zone_name, metres, None)
        for team, zone_name, metres in found.values()
        if team.id not in in_chain
    ]
    return choices


def case_detail(session: Session, case: Case) -> dict[str, Any]:
    """Everything known about one case, for the detail panel. No phone numbers."""
    lat, lng = session.execute(
        select(_latitude(Case.location), _longitude(Case.location)).where(Case.id == case.id)
    ).one()
    zone = session.get(Zone, case.zone_id) if case.zone_id else None
    team = session.get(Team, case.assigned_team_id) if case.assigned_team_id else None
    merged_into = session.get(Case, case.merged_into_id) if case.merged_into_id else None

    reports = session.scalars(select(Report).where(Report.case_id == case.id).order_by(Report.id)).all()
    reporters: dict[str, str] = {}
    for report in reports:
        reporters.setdefault(report.reporter_number, f"Reporter {len(reporters) + 1}")
    report_ids = [report.id for report in reports]
    photos = session.scalars(
        select(Photo).where(Photo.report_id.in_(report_ids)).order_by(Photo.id)
    ).all()

    # Duplicates merged into this case keep their own early events; show them too.
    merged = dict(
        session.execute(select(Case.id, Case.public_id).where(Case.merged_into_id == case.id)).all()
    )
    events = session.scalars(
        select(Event)
        .where(
            or_(
                Event.case_id.in_([case.id, *merged]),
                and_(
                    Event.case_id.is_(None),
                    Event.type.in_(INTAKE_EVENTS),
                    Event.data["report_id"].astext.in_([str(i) for i in report_ids]),
                ),
            )
        )
        .order_by(Event.created_at, Event.id)
    ).all()
    team_names = dict(session.execute(select(Team.phone, Team.name)).all())

    triaged = [
        e for e in events
        if e.case_id == case.id and e.type == "state_changed" and e.to_state == S.TRIAGED
    ]
    triage_reason = (triaged[-1].data or {}).get("reason") if triaged else None
    exhausted = any(e.case_id == case.id and e.type == "chain_exhausted" for e in events)

    dispatches = session.execute(
        select(Dispatch, Team.name)
        .join(Team, Dispatch.team_id == Team.id)
        .where(Dispatch.case_id == case.id)
        .order_by(Dispatch.id)
    ).all()

    can_assign = case.state in STAFF_CAN_ASSIGN and case.zone_id is not None
    return {
        "id": case.public_id,
        "state": case.state,
        "state_label": STATE_WORDS.get(case.state, case.state),
        "open": case.state in OPEN_STATES,
        "attention": _attention(case, exhausted),
        "is_demo": case.is_demo,
        "created_at": case.created_at.isoformat(),
        "latitude": lat,
        "longitude": lng,
        "merged_into": merged_into.public_id if merged_into else None,
        "zone": zone.slug if zone else None,
        "zone_name": zone.short_name if zone else None,
        "zone_is_approximate": bool(case.zone_is_approximate),
        "team": team.name if team else None,
        "triage": {
            "status": case.triage_status,  # "ok", "needs_review", or None while waiting
            "reason": _reason_words(triage_reason) if triage_reason else None,
            "at": case.triaged_at.isoformat() if case.triaged_at else None,
            "species": case.species,
            "injury_type": case.injury_type,
            "urgency": case.urgency,
            "aggression_risk": case.aggression_risk,
            "first_aid": case.first_aid or [],
        },
        "photos": [
            {"id": photo.id, "url": photo_url(photo.id), "at": photo.created_at.isoformat()}
            for photo in photos
        ],
        "reports": len(reports),
        "reporters": len(reporters),
        "notes": [
            {"reporter": reporters[r.reporter_number], "text": r.text, "at": r.created_at.isoformat()}
            for r in reports
            if r.text
        ],
        "dispatches": [
            {
                "team": team_name,
                "status": dispatch.status,
                "status_label": DISPATCH_WORDS.get(dispatch.status, dispatch.status),
                "sent_at": dispatch.created_at.isoformat(),
                "answered_at": dispatch.responded_at.isoformat() if dispatch.responded_at else None,
            }
            for dispatch, team_name in dispatches
        ],
        "events": [
            {
                "at": event.created_at.isoformat(),
                "label": (
                    f"Status: {STATE_WORDS.get(event.from_state, event.from_state or 'none')} "
                    f"to {STATE_WORDS.get(event.to_state, event.to_state)}"
                    if event.type == "state_changed"
                    else EVENT_WORDS.get(event.type, event.type.replace("_", " ").capitalize())
                ),
                "details": _event_details(event),
                "actor": _actor_words(event.actor, team_names, reporters),
                "from_case": merged.get(event.case_id),
            }
            for event in events
        ],
        "can_assign": can_assign,
        "can_cancel": case.state in OPEN_STATES and can_transition(case.state, S.CANCELLED),
        "team_choices": team_choices(session, case) if can_assign else [],
    }


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
        "response_times": response_times(session),
    }
