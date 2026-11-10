"""The case lifecycle. Every state change in the app goes through transition().

TRANSITIONS is the whole rulebook: for each state, the states a case may move
to next. Anything not listed is refused. Each successful move is written to
the audit log.
"""

from typing import Any

from sqlalchemy.orm import Session

from app.cases.audit import log_event
from app.cases.models import Case
from app.cases.models import CaseState as S

TRANSITIONS: dict[S, set[S]] = {
    S.REPORTED: {S.TRIAGED, S.CANCELLED},
    S.TRIAGED: {S.NEW, S.MERGED, S.CANCELLED},
    S.NEW: {S.ROUTED, S.CANCELLED},
    S.ROUTED: {S.ACCEPTED, S.ESCALATED, S.CANCELLED},
    S.ESCALATED: {S.ROUTED, S.ACCEPTED, S.CANCELLED},
    S.ACCEPTED: {S.ON_SITE, S.CANCELLED},
    S.ON_SITE: {S.RESOLVED, S.CANCELLED},
    # Final states: nothing follows.
    S.MERGED: set(),
    S.RESOLVED: set(),
    S.CANCELLED: set(),
}


class InvalidTransition(Exception):
    def __init__(self, from_state: str, to_state: str) -> None:
        super().__init__(f"A case cannot go from {from_state} to {to_state}")
        self.from_state = from_state
        self.to_state = to_state


def can_transition(from_state: str, to_state: str) -> bool:
    return S(to_state) in TRANSITIONS[S(from_state)]


def transition(
    session: Session,
    case: Case,
    to_state: S,
    *,
    actor: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    """Move a case to `to_state`, or raise InvalidTransition."""
    from_state = case.state
    if not can_transition(from_state, to_state):
        raise InvalidTransition(from_state, to_state)
    case.state = to_state
    log_event(
        session,
        "state_changed",
        case_id=case.id,
        actor=actor,
        from_state=from_state,
        to_state=to_state,
        data=data,
    )
