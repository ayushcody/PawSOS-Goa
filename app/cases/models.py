"""Tables for cases, the reports that make them, their photos, and the audit log.

One case can have several reports (slice 4 merges duplicates). A report with
no case yet is a draft: we are still waiting for its photo or its location.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class CaseState(StrEnum):
    REPORTED = "REPORTED"
    TRIAGED = "TRIAGED"
    MERGED = "MERGED"
    NEW = "NEW"
    ROUTED = "ROUTED"
    ESCALATED = "ESCALATED"
    ACCEPTED = "ACCEPTED"
    ON_SITE = "ON_SITE"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


def _point() -> Geography:
    # SRID 4326 is ordinary GPS latitude/longitude. The index is made in the migration.
    return Geography(geometry_type="POINT", srid=4326, spatial_index=False)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str | None] = mapped_column(String(16), unique=True)  # "PAW-0042"
    state: Mapped[str] = mapped_column(String(20))
    location: Mapped[Any] = mapped_column(_point())

    # Filled in by triage (slice 3). Empty until then.
    species: Mapped[str | None] = mapped_column(String(20))
    injury_type: Mapped[str | None] = mapped_column(String(200))
    urgency: Mapped[str | None] = mapped_column(String(10))
    aggression_risk: Mapped[str | None] = mapped_column(String(10))
    first_aid: Mapped[list[str] | None] = mapped_column(JSONB)
    triage_status: Mapped[str | None] = mapped_column(String(20))  # "ok" or "needs_review"
    triaged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Filled in by routing (slice 4).
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("zones.id"), index=True)
    zone_is_approximate: Mapped[bool | None] = mapped_column()
    merged_into_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"))

    # Filled in when a team accepts (slice 5).
    assigned_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    reports: Mapped[list["Report"]] = relationship(back_populates="case")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), index=True)
    reporter_number: Mapped[str] = mapped_column(String(20), index=True)
    location: Mapped[Any | None] = mapped_column(_point())
    text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case: Mapped[Case | None] = relationship(back_populates="reports")
    photos: Mapped[list["Photo"]] = relationship(back_populates="report")


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), index=True)
    path: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    report: Mapped[Report] = relationship(back_populates="photos")


class Event(Base):
    """The audit log. Rows are only ever added, never changed."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), index=True)
    type: Mapped[str] = mapped_column(String(50))
    from_state: Mapped[str | None] = mapped_column(String(20))
    to_state: Mapped[str | None] = mapped_column(String(20))
    actor: Mapped[str | None] = mapped_column(String(50))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
