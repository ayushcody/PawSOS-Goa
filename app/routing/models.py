"""Zones (the 14 urban local bodies) and the teams that answer for them."""

from datetime import time
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import Boolean, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Zone(Base):
    """A service area: an approximate centre point and radius, not a true boundary."""

    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    short_name: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(20))  # "corporation" or "council"
    taluka: Mapped[str] = mapped_column(String(40))
    district: Mapped[str] = mapped_column(String(20))
    centre: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    radius_m: Mapped[int] = mapped_column(Integer)
    approximate: Mapped[bool] = mapped_column(Boolean, default=True)

    teams: Mapped[list["Team"]] = relationship(back_populates="zone")


class Team(Base):
    """Someone who can be alerted: a zone's partner team, or a taluka officer."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    kind: Mapped[str] = mapped_column(String(20))  # "partner" or "taluka_officer"
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("zones.id"), index=True)
    taluka: Mapped[str | None] = mapped_column(String(40))  # set for taluka officers
    # Opening hours in Goa time. Both empty means always open.
    opens_at: Mapped[time | None] = mapped_column(Time)
    closes_at: Mapped[time | None] = mapped_column(Time)

    zone: Mapped[Zone | None] = relationship(back_populates="teams")
