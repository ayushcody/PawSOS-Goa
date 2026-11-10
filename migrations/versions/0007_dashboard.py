"""Demo-data flags and sterilisation counts for the dashboard.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A constant default means Postgres adds these without rewriting the table.
    for table in ("cases", "bite_reports"):
        op.add_column(
            table, sa.Column("is_demo", sa.Boolean, nullable=False, server_default=sa.false())
        )

    op.create_table(
        "sterilisation_counts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("zone_id", sa.Integer, sa.ForeignKey("zones.id"), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        # Empty means "we have no figure", which is different from zero.
        sa.Column("camps_held", sa.Integer),
        sa.Column("dogs_sterilised", sa.Integer),
        sa.UniqueConstraint("zone_id", "year"),
    )


def downgrade() -> None:
    op.drop_table("sterilisation_counts")
    op.drop_column("bite_reports", "is_demo")
    op.drop_column("cases", "is_demo")
