"""data integrity: dedupe keys, unique constraints, missing indexes

Revision ID: d1e2f3a4b5c6
Revises: c6d7e8f9a0b1
Create Date: 2026-08-01 18:00:00.000000

"""
from datetime import datetime
from typing import Sequence, Union
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op

from app.core.config import settings


# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "reminder_events",
        sa.Column("scheduled_local_date", sa.Date(), nullable=False, server_default="1970-01-01"),
    )
    op.add_column(
        "reminder_events",
        sa.Column("dedupe_key", sa.String(length=190), nullable=False, server_default="legacy"),
    )

    _backfill_reminder_events()
    _cleanup_duplicate_legacy_events()

    op.create_index(
        "uq_reminder_events_user_dedupe",
        "reminder_events",
        ["user_id", "dedupe_key"],
        unique=True,
    )
    op.create_index(
        "ix_reminder_events_local_date", "reminder_events", ["scheduled_local_date"]
    )
    op.create_index("uq_telegram_accounts_user_id", "telegram_accounts", ["user_id"], unique=True)
    op.create_index(
        "uq_user_responses_current_per_event",
        "user_responses",
        ["reminder_event_id"],
        unique=True,
        sqlite_where=sa.text("is_current = 1"),
        postgresql_where=sa.text("is_current = true"),
    )
    op.create_index(
        "ix_notification_logs_reminder_event", "notification_logs", ["reminder_event_id"]
    )
    op.create_index("ix_audit_logs_user_created", "audit_logs", ["user_id", "created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_audit_logs_user_created", table_name="audit_logs")
    op.drop_index("ix_notification_logs_reminder_event", table_name="notification_logs")
    op.drop_index("uq_user_responses_current_per_event", table_name="user_responses")
    op.drop_index("uq_telegram_accounts_user_id", table_name="telegram_accounts")
    op.drop_index("ix_reminder_events_local_date", table_name="reminder_events")
    op.drop_index("uq_reminder_events_user_dedupe", table_name="reminder_events")
    op.drop_column("reminder_events", "dedupe_key")
    op.drop_column("reminder_events", "scheduled_local_date")


def _backfill_reminder_events() -> None:
    conn = op.get_bind()
    server_tz = ZoneInfo(settings.timezone)
    user_tz_names = {
        row.user_id: row.timezone
        for row in conn.execute(sa.text("SELECT id AS user_id, timezone FROM users"))
    }

    rows = conn.execute(
        sa.text(
            "SELECT id, user_id, bot_key, related_type, related_id, scheduled_at "
            "FROM reminder_events"
        )
    )
    for row in rows:
        tz_name = user_tz_names.get(row.user_id) or settings.timezone
        scheduled = datetime.fromisoformat(row.scheduled_at)
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=server_tz)
        local_date = scheduled.astimezone(ZoneInfo(tz_name)).date().isoformat()
        related_type = row.related_type or "none"
        related_id = row.related_id if row.related_id is not None else 0
        dedupe_key = f"{row.bot_key}:{related_type}:{related_id}:{local_date}"

        conn.execute(
            sa.text(
                "UPDATE reminder_events "
                "SET scheduled_local_date = :d, dedupe_key = :k WHERE id = :id"
            ),
            {"d": local_date, "k": dedupe_key, "id": row.id},
        )


def _cleanup_duplicate_legacy_events() -> None:
    conn = op.get_bind()
    duplicate_groups = conn.execute(
        sa.text(
            "SELECT user_id, dedupe_key, MIN(id) AS keep_id "
            "FROM reminder_events "
            "GROUP BY user_id, dedupe_key "
            "HAVING COUNT(*) > 1"
        )
    )
    for group in duplicate_groups:
        dup_ids = conn.execute(
            sa.text(
                "SELECT id FROM reminder_events "
                "WHERE user_id = :u AND dedupe_key = :k AND id != :keep "
                "ORDER BY id"
            ),
            {"u": group.user_id, "k": group.dedupe_key, "keep": group.keep_id},
        )
        for dup in dup_ids:
            conn.execute(
                sa.text(
                    "UPDATE reminder_events "
                    "SET status = 'cancelled', dedupe_key = dedupe_key || ':dup:' || id "
                    "WHERE id = :id"
                ),
                {"id": dup.id},
            )
