"""Team alerts (dispatches) and the team a case is assigned to.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dispatches",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("case_id", sa.Integer, sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("team_id", sa.Integer, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),  # place in the escalation chain
        # sent, accepted, declined, timed_out, skipped_closed, cancelled
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("responded_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_dispatches_case_id", "dispatches", ["case_id"])
    # The timeout job looks up "sent and past its deadline" every few seconds.
    op.create_index("ix_dispatches_status_expires", "dispatches", ["status", "expires_at"])

    op.add_column("cases", sa.Column("assigned_team_id", sa.Integer, sa.ForeignKey("teams.id")))


def downgrade() -> None:
    op.drop_column("cases", "assigned_team_id")
    op.drop_table("dispatches")
