"""What staff can do to a case from the dashboard, besides assigning a team.

Assigning a team lives in app/routing/dispatch.py (assign_team), beside the
rest of the alerting. Like that module, this one only changes the database and
returns the messages to send; the route commits first, then delivers them.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock, messages
from app.cases import state_machine
from app.cases.models import Case
from app.cases.models import CaseState as S
from app.channels.base import Outbound
from app.contacts import language_for
from app.routing.flow import reporters_of
from app.routing.models import Dispatch, Team


def cancel_case(session: Session, case: Case, reason: str, actor: str = "staff") -> list[Outbound]:
    """Close an open case. Raises InvalidTransition if it is already closed.

    The reason stays in the audit log for staff; reporters get a calm, general
    message without it, because a note written for colleagues may not suit them.
    """
    state_machine.transition(session, case, S.CANCELLED, actor=actor, data={"reason": reason})

    outbox: list[Outbound] = []
    told: set[int] = set()
    waiting = session.scalars(
        select(Dispatch).where(Dispatch.case_id == case.id, Dispatch.status == "sent")
    ).all()
    for dispatch in waiting:
        dispatch.status = "cancelled"
        dispatch.responded_at = clock.now()
        told.add(dispatch.team_id)
    if case.assigned_team_id is not None:
        told.add(case.assigned_team_id)  # a team already on its way must be told too
    for team_id in sorted(told):
        team = session.get(Team, team_id)
        outbox.append(_msg(team.phone, "team_case_cancelled_by_staff", case))

    outbox += [
        _msg(number, "citizen_cancelled", case, language_for(session, number))
        for number in reporters_of(session, case)
    ]
    return outbox


def _msg(to: str, key: str, case: Case, language: str | None = None) -> Outbound:
    return Outbound(to=to, text=messages.render(key, language, case_id=case.public_id))
