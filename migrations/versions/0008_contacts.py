"""Each person's language, remembered by phone number.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("number", sa.String(20), primary_key=True),
        # Empty means "never chosen", which is answered in English.
        sa.Column("language", sa.String(8)),
        # When we sent the LANGUAGE menu; empty once they have answered.
        sa.Column("language_menu_at", sa.DateTime(timezone=True)),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("contacts")
