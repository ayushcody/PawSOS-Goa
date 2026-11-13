"""After a rescue: the team's photo of the animal, and the reporter's rating.

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rescue_photos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("case_id", sa.Integer, sa.ForeignKey("cases.id"), nullable=False, index=True),
        sa.Column("team_id", sa.Integer, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("path", sa.String(255), nullable=False),
        sa.Column("mime", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "case_ratings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("case_id", sa.Integer, sa.ForeignKey("cases.id"), nullable=False, index=True),
        sa.Column("reporter_number", sa.String(20), nullable=False),
        # "good", "ok" or "poor": the three buttons the reporter is shown.
        sa.Column("score", sa.String(8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # One rating per person per case; tapping again changes it.
        sa.UniqueConstraint("case_id", "reporter_number", name="uq_case_ratings_case_reporter"),
        sa.CheckConstraint("score in ('good', 'ok', 'poor')", name="ck_case_ratings_score"),
    )


def downgrade() -> None:
    op.drop_table("case_ratings")
    op.drop_table("rescue_photos")
