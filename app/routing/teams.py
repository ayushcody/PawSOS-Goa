"""Who gets alerted, and in what order.

The chain for a zone is: its own partner team, then the nearest neighbouring
zone's partner team, then the taluka officer. Slice 5 walks this chain.
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.routing.models import Team, Zone
from app.routing.zones import zones_by_distance

GOA_TIME = ZoneInfo("Asia/Kolkata")


def is_open(opens_at: time | None, closes_at: time | None, now: time) -> bool:
    """Is a team with these hours open at `now`?

    No hours at all means always open. Opening time is included, closing time
    is not: a team open 08:00 to 20:00 is open at 08:00 and closed at 20:00.

    TODO(me): Ayush extends this. It is wrong for a team that works overnight,
    for example 20:00 to 06:00: at 23:00 the line below says "closed", because
    23:00 is not before 06:00. Make overnight hours work, then remove the
    @pytest.mark.skip on test_is_open_overnight in tests/test_slice4.py and run:
        .venv/bin/pytest -q tests/test_slice4.py -k open

    Hint: you can tell hours are overnight because closes_at is earlier than
    opens_at. In that case "open" means now is after opening OR before closing.
    """
    if opens_at is None or closes_at is None:
        return True
    return opens_at <= now < closes_at


def team_is_open(team: Team, at: datetime | None = None) -> bool:
    moment = (at or datetime.now(GOA_TIME)).astimezone(GOA_TIME)
    return is_open(team.opens_at, team.closes_at, moment.time())


def _partner_teams(session: Session, zone: Zone) -> list[Team]:
    return list(
        session.scalars(
            select(Team).where(Team.zone_id == zone.id, Team.kind == "partner").order_by(Team.id)
        )
    )


def escalation_chain(session: Session, zone: Zone) -> list[Team]:
    chain = _partner_teams(session, zone)

    for neighbour in zones_by_distance(session, zone):
        neighbours_teams = _partner_teams(session, neighbour)
        if neighbours_teams:
            chain.append(neighbours_teams[0])
            break

    officer = session.scalar(
        select(Team).where(Team.kind == "taluka_officer", Team.taluka == zone.taluka).limit(1)
    )
    if officer is not None:
        chain.append(officer)
    return chain
