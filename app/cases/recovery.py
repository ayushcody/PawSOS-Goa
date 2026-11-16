"""Moving on cases that stalled before a team was alerted.

A new case normally goes REPORTED -> TRIAGED -> NEW -> ROUTED within seconds,
inside the request (or background task) that received the report. If the
server stops in the middle (a restart, a crash, a deploy), nothing would ever
pick that case up again. A rescue must never be lost that way.

So a scheduled job looks for real cases that have sat in REPORTED, TRIAGED or
NEW for longer than STUCK_AFTER, and finishes the work: a case still waiting
for triage goes on at high urgency, flagged for a person to look at its photo
(as when the model is unavailable), then it is merged or routed, and a team
is alerted. The reporter gets their case ID again, because they may never
have received it.

Like the rest of the case logic, this only changes the database and returns
the messages to send. The caller commits first, then delivers them.
"""

from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import messages
from app.cases.audit import log_event
from app.cases.models import Case
from app.cases.models import CaseState as S
from app.channels.base import Outbound
from app.contacts import language_for
from app.routing import dispatch
from app.routing.flow import reporters_of, route_case
from app.triage.flow import mark_for_review

# Longer than a normal triage call (the model's timeout is 60 seconds), so a
# photo still being looked at is not taken over. If it is, the state machine
# refuses the late triage result and the report flow stops quietly.
STUCK_AFTER = timedelta(minutes=2)
STUCK_STATES = (S.REPORTED, S.TRIAGED, S.NEW)
BATCH = 20  # at most this many cases per run; the rest wait for the next run


def stuck_condition():
    """Real cases that should have reached a team by now. Both times come from the database."""
    return (
        Case.state.in_(STUCK_STATES),
        Case.is_demo.is_(False),
        Case.updated_at <= func.now() - STUCK_AFTER,
        # A NEW case with no area has nobody to alert (no zones loaded): left for staff.
        or_(Case.state != S.NEW, Case.zone_id.is_not(None)),
    )


def recover_stuck_cases(session: Session) -> list[Outbound]:
    ids = session.scalars(
        select(Case.id).where(*stuck_condition()).order_by(Case.id).limit(BATCH)
    ).all()
    outbox: list[Outbound] = []
    for case_id in ids:
        # Locked like a button tap or a cancel; a case someone is handling now waits for the next run.
        case = session.scalar(
            select(Case)
            .where(Case.id == case_id, *stuck_condition())
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
        if case is not None:
            outbox += _move_on(session, case)
    return outbox


def _move_on(session: Session, case: Case) -> list[Outbound]:
    reporters = reporters_of(session, case)
    log_event(session, "case_recovered", case_id=case.id, actor="recovery", data={"from_state": case.state})

    if case.state == S.REPORTED:
        mark_for_review(session, case, "triage did not finish")

    if case.state == S.TRIAGED:
        outcome = route_case(session, case)
        if outcome.merged_into is not None:
            primary = outcome.merged_into
            return [
                _tell(session, number, "merged_new_reporter", case_id=primary.public_id)
                for number in reporters
            ]

    sent = dispatch.start_dispatch(session, case) if case.zone_id is not None else []
    # The team's alert first. Then the reporters' case ID (they may never have had it),
    # then anything dispatch says to them ("no team yet").
    told = [_tell(session, number, "case_created", case_id=case.public_id) for number in reporters]
    return (
        [m for m in sent if m.to not in reporters] + told + [m for m in sent if m.to in reporters]
    )


def _tell(session: Session, number: str, key: str, **values: object) -> Outbound:
    return Outbound(to=number, text=messages.render(key, language_for(session, number), **values))
