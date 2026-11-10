"""Which zone does a case fall in?

Zones are a centre point and a radius. We pick the nearest centre. If the
case is outside that zone's radius we still use it (someone must own the
case) but record that the match is approximate.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cases.models import Case
from app.routing.models import Zone


@dataclass
class ZoneMatch:
    zone: Zone
    distance_m: float
    within_radius: bool


def _case_location(case: Case):
    # Compare inside the database, so PostGIS does the geography.
    return select(Case.location).where(Case.id == case.id).scalar_subquery()


def find_zone(session: Session, case: Case) -> ZoneMatch | None:
    distance = func.ST_Distance(Zone.centre, _case_location(case)).label("distance")
    row = session.execute(select(Zone, distance).order_by(distance).limit(1)).first()
    if row is None:
        return None  # no zones loaded
    zone, metres = row
    return ZoneMatch(zone=zone, distance_m=float(metres), within_radius=metres <= zone.radius_m)


def zones_by_distance(session: Session, from_zone: Zone) -> list[Zone]:
    """Every other zone, nearest first."""
    here = select(Zone.centre).where(Zone.id == from_zone.id).scalar_subquery()
    return list(
        session.scalars(
            select(Zone).where(Zone.id != from_zone.id).order_by(func.ST_Distance(Zone.centre, here))
        )
    )
