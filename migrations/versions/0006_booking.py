"""Camps, slots, bookings and booking drafts.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _timestamp(name: str, **kwargs) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), **kwargs)


def upgrade() -> None:
    op.create_table(
        "camps",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String(60), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("short_name", sa.String(40), nullable=False),
        sa.Column("services", sa.String(80), nullable=False),
        sa.Column("venue", sa.String(160), nullable=False),
        sa.Column("zone_id", sa.Integer, sa.ForeignKey("zones.id")),
        sa.Column(
            "location",
            Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
    )

    op.create_table(
        "camp_slots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("camp_id", sa.Integer, sa.ForeignKey("camps.id"), nullable=False),
        _timestamp("starts_at", nullable=False),
        _timestamp("ends_at", nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.UniqueConstraint("camp_id", "starts_at"),
    )
    op.create_index("ix_camp_slots_camp_id", "camp_slots", ["camp_id"])

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slot_id", sa.Integer, sa.ForeignKey("camp_slots.id"), nullable=False),
        sa.Column("camp_id", sa.Integer, sa.ForeignKey("camps.id"), nullable=False),
        sa.Column("owner_number", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="booked"),
        sa.Column("calendar_event_id", sa.String(200)),
        _timestamp("reminder_sent_at"),
        _timestamp("created_at", server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bookings_slot_id", "bookings", ["slot_id"])
    op.create_index("ix_bookings_camp_id", "bookings", ["camp_id"])
    op.create_index("ix_bookings_owner_number", "bookings", ["owner_number"])

    op.create_table(
        "booking_drafts",
        sa.Column("owner_number", sa.String(20), primary_key=True),
        sa.Column("camp_id", sa.Integer, sa.ForeignKey("camps.id")),
        sa.Column("options", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        _timestamp("updated_at", nullable=False),
    )


def downgrade() -> None:
    op.drop_table("booking_drafts")
    op.drop_table("bookings")
    op.drop_table("camp_slots")
    op.drop_table("camps")
