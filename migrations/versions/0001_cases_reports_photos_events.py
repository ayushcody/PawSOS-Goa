"""Cases, reports, photos and the events audit log.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _point() -> Geography:
    return Geography(geometry_type="POINT", srid=4326, spatial_index=False)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "cases",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("public_id", sa.String(16), unique=True),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("location", _point(), nullable=False),
        _created_at(),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    # A GiST index is what makes "cases near this point" fast (slice 4 dedup).
    op.create_index("ix_cases_location", "cases", ["location"], postgresql_using="gist")
    op.create_index("ix_cases_state", "cases", ["state"])

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("case_id", sa.Integer, sa.ForeignKey("cases.id")),
        sa.Column("reporter_number", sa.String(20), nullable=False),
        sa.Column("location", _point()),
        sa.Column("text", sa.Text),
        _created_at(),
    )
    op.create_index("ix_reports_case_id", "reports", ["case_id"])
    op.create_index("ix_reports_reporter_number", "reports", ["reporter_number"])

    op.create_table(
        "photos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("report_id", sa.Integer, sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("path", sa.String(255), nullable=False),
        sa.Column("mime", sa.String(50), nullable=False),
        _created_at(),
    )
    op.create_index("ix_photos_report_id", "photos", ["report_id"])

    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("case_id", sa.Integer, sa.ForeignKey("cases.id")),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("from_state", sa.String(20)),
        sa.Column("to_state", sa.String(20)),
        sa.Column("actor", sa.String(50)),
        sa.Column("data", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        _created_at(),
    )
    op.create_index("ix_events_case_id", "events", ["case_id"])


def downgrade() -> None:
    op.drop_table("events")
    op.drop_table("photos")
    op.drop_table("reports")
    op.drop_table("cases")
