"""Camps, their time slots, bookings, and the half-finished BOOK conversation."""

from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Camp(Base):
    __tablename__ = "camps"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    short_name: Mapped[str] = mapped_column(String(40))
    services: Mapped[str] = mapped_column(String(80))
    venue: Mapped[str] = mapped_column(String(160))
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("zones.id"))
    location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )

    slots: Mapped[list["CampSlot"]] = relationship(back_populates="camp", order_by="CampSlot.starts_at")


class CampSlot(Base):
    __tablename__ = "camp_slots"
    __table_args__ = (UniqueConstraint("camp_id", "starts_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    camp_id: Mapped[int] = mapped_column(ForeignKey("camps.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int] = mapped_column(Integer)

    camp: Mapped[Camp] = relationship(back_populates="slots")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("camp_slots.id"), index=True)
    camp_id: Mapped[int] = mapped_column(ForeignKey("camps.id"), index=True)
    owner_number: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), default="booked")
    # Set when the slot has been put on the camp's Google Calendar.
    calendar_event_id: Mapped[str | None] = mapped_column(String(200))
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    slot: Mapped[CampSlot] = relationship()

    @property
    def reference(self) -> str:
        return f"BK-{self.id:04d}"


class BookingDraft(Base):
    """Where someone is in the BOOK conversation. One row per phone number."""

    __tablename__ = "booking_drafts"

    owner_number: Mapped[str] = mapped_column(String(20), primary_key=True)
    camp_id: Mapped[int | None] = mapped_column(ForeignKey("camps.id"))  # empty: still choosing a camp
    # The ids behind the numbered list we last showed, in order. "2" means options[1].
    options: Mapped[list[int]] = mapped_column(JSONB, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
