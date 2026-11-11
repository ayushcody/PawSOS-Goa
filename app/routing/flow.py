"""After triage: merge the case into an existing one, or make it NEW in a zone."""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cases import state_machine
from app.cases.audit import log_event
from app.cases.models import Case, CaseState, Report
from app.routing import dedup
from app.routing.models import Zone
from app.routing.zones import find_zone

URGENCY_ORDER = {None: 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
CLOSED = {CaseState.MERGED, CaseState.RESOLVED, CaseState.CANCELLED}


@dataclass
class RoutingOutcome:
    merged_into: Case | None = None
    earlier_reporters: list[str] = field(default_factory=list)  # who had already reported it
    report_count: int = 0
    zone: Zone | None = None


def reporters_of(session: Session, case: Case) -> list[str]:
    """The people to keep informed about a case: everyone who reported it and has not withdrawn.

    A person who withdrew and then reported the animal again has a new report,
    so they are back on the list.
    """
    numbers = session.scalars(
        select(Report.reporter_number)
        .where(Report.case_id == case.id, Report.withdrawn_at.is_(None))
        .order_by(Report.id)
    )
    return list(dict.fromkeys(numbers))  # unique, in order


def route_case(session: Session, case: Case) -> RoutingOutcome:
    primary = dedup.find_duplicate(session, case)
    if primary is not None:
        # Lock it, so a reporter cancelling it right now and this merge happen one after
        # the other. If it closed meanwhile, this report becomes a case of its own.
        session.refresh(primary, with_for_update=True)
        if primary.state not in CLOSED:
            return _merge(session, case, primary)

    match = find_zone(session, case)
    if match is not None:
        case.zone_id = match.zone.id
        case.zone_is_approximate = not match.within_radius
        log_event(
            session,
            "zone_assigned",
            case_id=case.id,
            actor="routing",
            data={
                "zone": match.zone.slug,
                "distance_m": round(match.distance_m),
                "within_radius": match.within_radius,
            },
        )
    state_machine.transition(session, case, CaseState.NEW, actor="routing")
    return RoutingOutcome(zone=match.zone if match else None)


def _merge(session: Session, case: Case, primary: Case) -> RoutingOutcome:
    earlier = reporters_of(session, primary)

    # The reports move to the case that stays open, so it knows every reporter.
    for report in session.scalars(select(Report).where(Report.case_id == case.id)):
        report.case_id = primary.id

    # Two people may see it differently. Keep the more urgent reading.
    if URGENCY_ORDER[case.urgency] > URGENCY_ORDER[primary.urgency]:
        log_event(
            session,
            "urgency_raised",
            case_id=primary.id,
            actor="routing",
            data={"from": primary.urgency, "to": case.urgency, "because_of": case.public_id},
        )
        primary.urgency = case.urgency

    case.merged_into_id = primary.id
    state_machine.transition(
        session, case, CaseState.MERGED, actor="routing", data={"merged_into": primary.public_id}
    )
    log_event(
        session,
        "report_merged_in",
        case_id=primary.id,
        actor="routing",
        data={"from_case": case.public_id},
    )
    session.flush()
    count = len(session.scalars(select(Report.id).where(Report.case_id == primary.id)).all())
    return RoutingOutcome(merged_into=primary, earlier_reporters=earlier, report_count=count)
