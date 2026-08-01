"""add reminder notify_after

Revision ID: f4e5d6c7b8a9
Revises: e2f3a4b5c6d7
Create Date: 2026-08-01 20:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f4e5d6c7b8a9"
down_revision: Union[str, Sequence[str], None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "reminder_events",
        sa.Column("notify_after", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_reminder_events_due",
        "reminder_events",
        ["status", "scheduled_at", "notify_after"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_reminder_events_due", table_name="reminder_events")
    op.drop_column("reminder_events", "notify_after")
