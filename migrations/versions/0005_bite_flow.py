"""Health centres and bite reports.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _point() -> Geography:
    return Geography(geometry_type="POINT", srid=4326, spatial_index=False)


def upgrade() -> None:
    op.create_table(
        "health_centres",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("location", _point(), nullable=False),
        sa.Column("verified", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_health_centres_location", "health_centres", ["location"], postgresql_using="gist"
    )

    op.create_table(
        "bite_reports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("reporter_number", sa.String(20), nullable=False),
        sa.Column("location", _point()),
        sa.Column("health_centre_id", sa.Integer, sa.ForeignKey("health_centres.id")),
        sa.Column("is_hotspot", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_bite_reports_reporter_number", "bite_reports", ["reporter_number"])
    op.create_index(
        "ix_bite_reports_location", "bite_reports", ["location"], postgresql_using="gist"
    )


def downgrade() -> None:
    op.drop_table("bite_reports")
    op.drop_table("health_centres")
