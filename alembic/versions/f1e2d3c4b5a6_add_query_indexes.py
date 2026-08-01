"""add query indexes

Revision ID: f1e2d3c4b5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-08-01 14:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f1e2d3c4b5a6"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index("ix_reminder_events_user_status", "reminder_events", ["user_id", "status"])
    op.create_index("ix_reminder_events_scheduled_at", "reminder_events", ["scheduled_at"])
    op.create_index(
        "ix_reminder_events_related", "reminder_events", ["related_type", "related_id"]
    )
    op.create_index(
        "ix_user_responses_event_current", "user_responses", ["reminder_event_id", "is_current"]
    )
    op.create_index("ix_user_responses_user_bot", "user_responses", ["user_id", "bot_key"])
    op.create_index("ix_notification_logs_user_sent", "notification_logs", ["user_id", "sent_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_notification_logs_user_sent", table_name="notification_logs")
    op.drop_index("ix_user_responses_user_bot", table_name="user_responses")
    op.drop_index("ix_user_responses_event_current", table_name="user_responses")
    op.drop_index("ix_reminder_events_related", table_name="reminder_events")
    op.drop_index("ix_reminder_events_scheduled_at", table_name="reminder_events")
    op.drop_index("ix_reminder_events_user_status", table_name="reminder_events")
