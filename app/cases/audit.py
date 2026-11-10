"""Write to the audit log. Every case event goes through here."""

from typing import Any

from sqlalchemy.orm import Session

from app.cases.models import Event


def log_event(
    session: Session,
    type: str,
    *,
    case_id: int | None = None,
    actor: str | None = None,
    from_state: str | None = None,
    to_state: str | None = None,
    data: dict[str, Any] | None = None,
) -> Event:
    event = Event(
        type=type,
        case_id=case_id,
        actor=actor,
        from_state=from_state,
        to_state=to_state,
        data=data or {},
    )
    session.add(event)
    return event
