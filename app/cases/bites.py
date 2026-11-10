"""The bite flow.

Someone says they were bitten. We answer at once with wash-the-wound guidance
and ask where they are. When the location arrives we name the nearest health
centre on our list and record the spot, so repeated bites in one place show
up as a hotspot.

A bite report is about a person, so it is kept apart from animal rescue cases.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from geoalchemy2 import Geography, Geometry
from sqlalchemy import Boolean, DateTime, ForeignKey, String, cast, false, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.cases.audit import log_event
from app.cases.geo import point
from app.db import Base

PENDING_WINDOW = timedelta(minutes=30)
HOTSPOT_RADIUS_M = 500
HOTSPOT_WINDOW = timedelta(days=30)
HOTSPOT_MIN_BITES = 3

# Whole words only, so "rabbit" and "habit" do not look like "bit".
# "bit" alone is ambiguous ("a bit of blood"), so it counts only when followed
# by who was bitten ("bit me", "bit a child") and not when it follows "a".
_BITE_WORDS = re.compile(
    r"\b(bite|bites|bitten|biting|got bit)\b"
    r"|(?<!\ba )\bbit (me|him|her|us|them|my|a|an|the|someone|somebody)\b"
    r"|काटा|काट लिया|चावला|चावलो",
    re.IGNORECASE,
)


def is_bite_report(text: str) -> bool:
    return bool(_BITE_WORDS.search(text))


def _point_column(nullable: bool):
    return mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=nullable
    )


class HealthCentre(Base):
    __tablename__ = "health_centres"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(40))
    location: Mapped[Any] = _point_column(nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class BiteReport(Base):
    __tablename__ = "bite_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_number: Mapped[str] = mapped_column(String(20), index=True)
    location: Mapped[Any | None] = _point_column(nullable=True)  # empty until they share it
    health_centre_id: Mapped[int | None] = mapped_column(ForeignKey("health_centres.id"))
    is_hotspot: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


@dataclass
class NearestCentre:
    name: str
    distance_km: float
    latitude: float
    longitude: float


@dataclass
class BiteOutcome:
    centre: NearestCentre | None
    bites_nearby: int
    is_hotspot: bool


def start(session: Session, number: str) -> BiteReport:
    """Record that this person was bitten. Their location comes next."""
    bite = pending_for(session, number)
    if bite is None:
        bite = BiteReport(reporter_number=number)
        session.add(bite)
        session.flush()
        log_event(session, "bite_reported", actor=number, data={"bite_report_id": bite.id})
    return bite


def pending_for(session: Session, number: str) -> BiteReport | None:
    """A recent bite report from this number that still has no location."""
    return session.scalar(
        select(BiteReport)
        .where(
            BiteReport.reporter_number == number,
            BiteReport.location.is_(None),
            BiteReport.created_at >= datetime.now(UTC) - PENDING_WINDOW,
        )
        .order_by(BiteReport.id.desc())
        .limit(1)
    )


def add_location(
    session: Session, bite: BiteReport, latitude: float, longitude: float
) -> BiteOutcome:
    bite.location = point(latitude, longitude)
    session.flush()
    here = select(BiteReport.location).where(BiteReport.id == bite.id).scalar_subquery()

    # Nearest health centre, with the distance worked out by PostGIS.
    distance = func.ST_Distance(HealthCentre.location, here).label("distance")
    row = session.execute(select(HealthCentre, distance).order_by(distance).limit(1)).first()
    centre = None
    if row is not None:
        found, metres = row
        bite.health_centre_id = found.id
        lat, lng = session.execute(
            select(
                func.ST_Y(cast(HealthCentre.location, Geometry)),  # latitude
                func.ST_X(cast(HealthCentre.location, Geometry)),  # longitude
            ).where(HealthCentre.id == found.id)
        ).one()
        # [VERIFY] is a note for us; the message to the person says the same in plain words.
        public_name = found.name.replace(" [VERIFY]", "")
        centre = NearestCentre(public_name, round(metres / 1000, 1), lat, lng)

    # How many bites (this one included) within 500 m in the last 30 days?
    nearby = session.scalar(
        select(func.count())
        .select_from(BiteReport)
        .where(
            BiteReport.location.is_not(None),
            BiteReport.created_at >= datetime.now(UTC) - HOTSPOT_WINDOW,
            func.ST_DWithin(BiteReport.location, here, HOTSPOT_RADIUS_M),
        )
    )
    bite.is_hotspot = nearby >= HOTSPOT_MIN_BITES
    log_event(
        session,
        "bite_located",
        actor=bite.reporter_number,
        data={
            "bite_report_id": bite.id,
            "latitude": latitude,
            "longitude": longitude,
            "health_centre": centre.name if centre else None,
            "bites_nearby": nearby,
            "is_hotspot": bite.is_hotspot,
        },
    )
    return BiteOutcome(centre=centre, bites_nearby=nearby, is_hotspot=bite.is_hotspot)
