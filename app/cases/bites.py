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
    """Does the message mention a bite at all? bite_kind() then says who was bitten."""
    return bool(_BITE_WORDS.search(text))


# Who was bitten. Only English is understood; a bite in Devanagari ("काटा") counts as a
# person's, as it always has, because that reply also asks about the animal.
_ANIMALS = (
    r"(?:dogs?|pupp(?:y|ies)|pups?|cats?|kittens?|cows?|calf|calves|bulls?|buffalo(?:es)?|goats?|"
    r"pigs?|monkeys?|birds?|crows?|pigeons?|horses?|donkeys?|animals?|strays?)"
)
_PEOPLE = (
    r"(?:child|children|boy|girl|man|woman|person|kid|baby|son|daughter|brother|sister|mother|father|"
    r"mom|mum|dad|friend|wife|husband|grandmother|grandfather|neighbou?r|hand|leg|arm|finger|foot|ankle)"
)
_PERSON_BITTEN = re.compile(
    r"\bi\s*(?:was|got|have been|'ve been|am|'m)\s+(?:bitten|bit)\b"
    # A message that starts "bitten by a dog" or "got bit by a stray" is about the sender.
    r"|^\W*(?:just\s+)?(?:got\s+)?(?:bitten|bit)\s+by\b"
    r"|\bbit(?:ten)?\s+me\b"
    r"|\b(?:my|our|a|the|this|that)\s+" + _PEOPLE + r"\s+(?:was|got|has been|is|have been)\s+(?:bitten|bit)\b"
    r"|\b(?:someone|somebody)\s+(?:was|got|has been|is)\s+(?:bitten|bit)\b"
    r"|\bbit\s+(?:him|her|us|them|someone|somebody|people)\b"
    # "bit my hand", "bit a child": anyone or anything that is not an animal.
    r"|(?<!\ba )\bbit\s+(?:my|our|a|an|the|this|that)\s+(?!(?:little\s+|small\s+|stray\s+|other\s+)?" + _ANIMALS + r"\b)"
    r"|काटा|काट लिया|चावला|चावलो",
    re.IGNORECASE,
)
_ANIMAL_BITTEN = re.compile(
    # "a dog has been bitten", "my cat was bitten", "the cow is bitten on its neck"
    r"\b" + _ANIMALS + r"\b[^.!?]{0,30}?\b(?:was|is|got|gets|has been|have been|been|being)\s+(?:bitten|bit)\b"
    # "a snake bit the dog", "dogs biting a calf". The word before the animal is required:
    # "a biting dog" is a dog that bites, not a dog that was bitten.
    r"|\b(?:bit|bites|biting)\s+(?:a|an|the|my|our|this|that|another|one|some|two|three)\s+"
    r"(?:little\s+|small\s+|stray\s+|other\s+)?" + _ANIMALS + r"\b",
    re.IGNORECASE,
)


def bite_kind(text: str) -> str | None:
    """Who was bitten: "person", "animal", "unclear", or None when no bite is mentioned.

    A person comes first when both are named: their reply is first aid, and it
    also asks for the animal's photo and location.
    """
    if not is_bite_report(text):
        return None
    if _PERSON_BITTEN.search(text):
        return "person"
    if _ANIMAL_BITTEN.search(text):
        return "animal"
    return "unclear"


# The two answers to "was a person bitten, or is an animal hurt?"
CHOICE_PERSON = "bite:person"
CHOICE_ANIMAL = "bite:animal"
CHOICES = (CHOICE_PERSON, CHOICE_ANIMAL)


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
