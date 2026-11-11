"""Turning messages into a case.

A case needs a photo and a location from the same number. They can arrive in
either order. Until both are here, the report is a draft (it has no case).
A draft older than DRAFT_WINDOW is ignored and a new one starts.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cases.audit import log_event
from app.cases.geo import point
from app.cases.models import Case, CaseState, Photo, Report

DRAFT_WINDOW = timedelta(minutes=30)


@dataclass
class IntakeResult:
    status: Literal["need_both", "need_location", "need_photo", "case_created"]
    case_id: str | None = None  # the public ID, e.g. "PAW-0042"
    case: Case | None = None


def format_case_id(number: int) -> str:
    return f"PAW-{number:04d}"


def _draft_for(session: Session, number: str) -> Report:
    """The sender's open draft, or a fresh one."""
    cutoff = datetime.now(UTC) - DRAFT_WINDOW
    draft = session.scalar(
        select(Report)
        .where(
            Report.reporter_number == number,
            Report.case_id.is_(None),
            Report.created_at >= cutoff,
        )
        .order_by(Report.created_at.desc())
        .limit(1)
    )
    if draft is None:
        draft = Report(reporter_number=number)
        session.add(draft)
        session.flush()  # sends the INSERT so draft.id exists
    return draft


def add_photo(session: Session, number: str, path: str, mime: str) -> IntakeResult:
    draft = _draft_for(session, number)
    session.add(Photo(report_id=draft.id, path=path, mime=mime))
    log_event(session, "photo_received", actor=number, data={"report_id": draft.id})
    return _open_case_if_complete(session, draft)


def add_location(session: Session, number: str, latitude: float, longitude: float) -> IntakeResult:
    draft = _draft_for(session, number)
    draft.location = point(latitude, longitude)
    log_event(
        session,
        "location_received",
        actor=number,
        data={"report_id": draft.id, "latitude": latitude, "longitude": longitude},
    )
    return _open_case_if_complete(session, draft)


def has_open_draft(session: Session, number: str) -> bool:
    """True while the person has sent a photo or a location but not yet both."""
    cutoff = datetime.now(UTC) - DRAFT_WINDOW
    return (
        session.scalar(
            select(Report.id)
            .where(
                Report.reporter_number == number,
                Report.case_id.is_(None),
                Report.created_at >= cutoff,
            )
            .limit(1)
        )
        is not None
    )


def add_note(
    session: Session, number: str, text: str, language: str | None, *, spoken: bool = True
) -> IntakeResult:
    """Keep what the person said or typed about the animal with their report."""
    draft = _draft_for(session, number)
    draft.text = f"{draft.text} {text}" if draft.text else text
    log_event(
        session,
        "voice_note_received" if spoken else "description_typed",
        actor=number,
        data={"report_id": draft.id, "language": language, "characters": len(text)},
    )
    return _open_case_if_complete(session, draft)


def _open_case_if_complete(session: Session, draft: Report) -> IntakeResult:
    session.flush()
    photo_count = session.scalar(
        select(func.count()).select_from(Photo).where(Photo.report_id == draft.id)
    )
    if draft.location is None and not photo_count:
        return IntakeResult("need_both")
    if draft.location is None:
        return IntakeResult("need_location")
    if not photo_count:
        return IntakeResult("need_photo")

    case = Case(state=CaseState.REPORTED, location=draft.location)
    session.add(case)
    session.flush()  # the database hands out case.id here
    case.public_id = format_case_id(case.id)
    draft.case_id = case.id
    log_event(
        session,
        "case_created",
        case_id=case.id,
        actor=draft.reporter_number,
        to_state=CaseState.REPORTED,
        data={"report_id": draft.id, "photos": photo_count},
    )
    return IntakeResult("case_created", case_id=case.public_id, case=case)
