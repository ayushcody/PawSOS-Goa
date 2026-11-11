"""A reporter can withdraw from a case that other people also reported.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Empty for almost every report. Set when the reporter sends CANCEL on a shared
    # case: they stop getting updates, and the case stays open for the others.
    op.add_column("reports", sa.Column("withdrawn_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("reports", "withdrawn_at")
