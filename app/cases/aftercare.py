"""After a case is resolved: the team's photo of the animal, and the reporter's rating.

    team taps Resolved        -> each reporter is told, then asked "How did it go?"
                                 with three buttons (Good, OK, Poor)
    reporter taps a button    -> the rating is saved; tapping another changes it
    team sends a photo        -> if it arrives within PHOTO_WINDOW of resolving a
                                 case, it is passed to everyone who reported it

Like the rest of the case logic, this module only changes the database and
returns the messages to send. The caller commits first, then delivers them.
"""

import re
from datetime import datetime, timedelta

from sqlalchemy import DateTime, ForeignKey, String, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from app import messages
from app.cases.audit import log_event
from app.cases.models import Case, Event
from app.cases.models import CaseState as S
from app.channels.base import Button, Outbound
from app.contacts import language_for
from app.db import Base
from app.routing.flow import reporters_of
from app.routing.models import Team

# A photo from a team's number counts as the rescue photo only this soon after
# the team resolved a case. After that, a photo from them is a new report.
PHOTO_WINDOW = timedelta(minutes=30)
SCORES = ("good", "ok", "poor")
RATING_ID = re.compile(r"^rate:(PAW-\d{4,}):(good|ok|poor)$")


class RescuePhoto(Base):
    """A photo the team sent after attending to the animal."""

    __tablename__ = "rescue_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    path: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Rating(Base):
    """What one reporter said about how their case went."""

    __tablename__ = "case_ratings"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    reporter_number: Mapped[str] = mapped_column(String(20))
    score: Mapped[str] = mapped_column(String(8))  # one of SCORES
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def satisfaction_percent(good: int, ok: int, poor: int) -> int | None:
    """The share of ratings that were "good", as a whole percentage.

    TODO(me): Ayush writes this. It returns None for now, so the dashboard
    shows the three counts but no percentage.
    Make it return the share of "good" among all ratings, rounded to a whole
    number: (3, 1, 0) -> 75, (1, 1, 1) -> 33, (2, 0, 0) -> 100.
    With no ratings at all it must still return None: "no ratings yet" is not
    the same as 0%. (This project never shows an unknown as a zero.)
    Then remove the @pytest.mark.skip on test_satisfaction_percent in
    tests/test_aftercare.py and run:
        .venv/bin/pytest -q tests/test_aftercare.py -k satisfaction
    Hint: round() gives the nearest whole number; watch out for dividing by zero.
    """
    return None


# ---------- the rating ----------


def rating_prompts(session: Session, case: Case) -> list[Outbound]:
    """Ask everyone who reported the case how it went, each in their own language."""
    outbox = []
    for number in reporters_of(session, case):
        language = language_for(session, number)
        outbox.append(
            Outbound(
                to=number,
                text=messages.render("rating_ask", language, case_id=case.public_id),
                buttons=[
                    Button(f"rate:{case.public_id}:{score}", messages.render(f"rating_{score}", language))
                    for score in SCORES
                ],
            )
        )
    return outbox


def is_rating(button_id: str) -> bool:
    return RATING_ID.match(button_id) is not None


def handle_rating(session: Session, number: str, button_id: str) -> list[Outbound]:
    """Save a reporter's rating. Only a person who reported a resolved case can rate it."""
    public_id, score = RATING_ID.match(button_id).groups()
    language = language_for(session, number)
    case = session.scalar(select(Case).where(Case.public_id == public_id))
    if case is None or case.state != S.RESOLVED or number not in reporters_of(session, case):
        return [Outbound(to=number, text=messages.render("rating_unavailable", language))]

    # One row per person per case: a second tap replaces the first.
    session.execute(
        insert(Rating)
        .values(case_id=case.id, reporter_number=number, score=score)
        .on_conflict_do_update(
            constraint="uq_case_ratings_case_reporter", set_={"score": score, "created_at": func.now()}
        )
    )
    log_event(session, "case_rated", case_id=case.id, actor=number, data={"score": score})
    return [Outbound(to=number, text=messages.render("rating_thanks", language, case_id=public_id))]


def rating_counts(session: Session, case_ids: list[int] | None = None) -> dict[str, int]:
    """How many good, ok and poor ratings there are, for these cases or for all."""
    query = select(Rating.score, func.count()).group_by(Rating.score)
    if case_ids is not None:
        query = query.where(Rating.case_id.in_(case_ids))
    found = dict(session.execute(query).all())
    return {score: found.get(score, 0) for score in SCORES}


# ---------- the rescue photo ----------


def case_awaiting_photo(session: Session, number: str) -> tuple[Case, Team] | None:
    """The case this team resolved a moment ago and has not yet sent a photo for.

    None for anyone who is not a team, and for a team with no such case, so
    their photo is treated as the start of an ordinary report.
    """
    team = session.scalar(select(Team).where(Team.phone == number))
    if team is None:
        return None
    resolved_at = (
        select(func.max(Event.created_at))
        .where(Event.case_id == Case.id, Event.to_state == S.RESOLVED)
        .correlate(Case)
        .scalar_subquery()
    )
    has_photo = select(RescuePhoto.id).where(RescuePhoto.case_id == Case.id).exists()
    case = session.scalar(
        select(Case)
        .where(
            Case.assigned_team_id == team.id,
            Case.state == S.RESOLVED,
            resolved_at >= func.now() - PHOTO_WINDOW,  # both stamped by the database
            ~has_photo,
        )
        .order_by(resolved_at.desc())
        .limit(1)
    )
    return (case, team) if case is not None else None


def add_rescue_photo(
    session: Session, case: Case, team: Team, media_name: str, mime: str
) -> list[Outbound]:
    """Keep the team's photo with the case and pass it to everyone who reported it."""
    session.add(RescuePhoto(case_id=case.id, team_id=team.id, path=media_name, mime=mime))
    log_event(
        session, "rescue_photo_received", case_id=case.id, actor=team.phone, data={"team": team.name}
    )
    outbox = [
        Outbound(to=team.phone, text=messages.render("team_photo_passed_on", case_id=case.public_id))
    ]
    for number in reporters_of(session, case):
        caption = messages.render(
            "rescue_photo_caption", language_for(session, number), case_id=case.public_id
        )
        outbox.append(Outbound(to=number, text=caption, media_name=media_name))
    return outbox
