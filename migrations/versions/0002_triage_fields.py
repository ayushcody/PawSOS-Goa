"""Triage results on cases.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

COLUMNS = [
    sa.Column("species", sa.String(20)),
    sa.Column("injury_type", sa.String(200)),
    sa.Column("urgency", sa.String(10)),
    sa.Column("aggression_risk", sa.String(10)),
    sa.Column("first_aid", JSONB),
    sa.Column("triage_status", sa.String(20)),  # "ok" or "needs_review"
    sa.Column("triaged_at", sa.DateTime(timezone=True)),
]


def upgrade() -> None:
    for column in COLUMNS:
        op.add_column("cases", column)


def downgrade() -> None:
    for column in reversed(COLUMNS):
        op.drop_column("cases", column.name)
