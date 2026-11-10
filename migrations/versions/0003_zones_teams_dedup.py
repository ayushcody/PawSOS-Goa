"""Zones, teams, and the case columns for routing and merging.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zones",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("short_name", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("taluka", sa.String(40), nullable=False),
        sa.Column("district", sa.String(20), nullable=False),
        sa.Column(
            "centre",
            Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("radius_m", sa.Integer, nullable=False),
        sa.Column("approximate", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_zones_centre", "zones", ["centre"], postgresql_using="gist")

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False, unique=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("zone_id", sa.Integer, sa.ForeignKey("zones.id")),
        sa.Column("taluka", sa.String(40)),
        sa.Column("opens_at", sa.Time),
        sa.Column("closes_at", sa.Time),
    )
    op.create_index("ix_teams_zone_id", "teams", ["zone_id"])

    op.add_column("cases", sa.Column("zone_id", sa.Integer, sa.ForeignKey("zones.id")))
    op.add_column("cases", sa.Column("zone_is_approximate", sa.Boolean))
    op.add_column("cases", sa.Column("merged_into_id", sa.Integer, sa.ForeignKey("cases.id")))
    op.create_index("ix_cases_zone_id", "cases", ["zone_id"])


def downgrade() -> None:
    op.drop_index("ix_cases_zone_id", table_name="cases")
    op.drop_column("cases", "merged_into_id")
    op.drop_column("cases", "zone_is_approximate")
    op.drop_column("cases", "zone_id")
    op.drop_table("teams")
    op.drop_table("zones")
