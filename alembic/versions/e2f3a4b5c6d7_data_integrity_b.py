"""data integrity b: check constraints, permanent server defaults

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-08-01 19:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("reminder_events") as batch_op:
        batch_op.alter_column(
            "scheduled_local_date",
            existing_type=sa.Date(),
            nullable=False,
            server_default=None,
        )
        batch_op.alter_column(
            "dedupe_key",
            existing_type=sa.String(length=190),
            nullable=False,
            server_default=None,
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )

    with op.batch_alter_table("habits") as batch_op:
        batch_op.create_check_constraint(
            "ck_habits_target_hour_range", "target_hour BETWEEN 0 AND 23"
        )
        batch_op.create_check_constraint(
            "ck_habits_target_minute_range", "target_minute BETWEEN 0 AND 59"
        )

    with op.batch_alter_table("users") as batch_op:
        batch_op.create_check_constraint(
            "ck_users_week_start_day_range", "week_start_day BETWEEN 1 AND 7"
        )
        batch_op.create_check_constraint(
            "ck_users_quiet_hours_start_format",
            "quiet_hours_start IS NULL OR "
            "(length(quiet_hours_start) = 5 AND substr(quiet_hours_start, 3, 1) = ':')",
        )
        batch_op.create_check_constraint(
            "ck_users_quiet_hours_end_format",
            "quiet_hours_end IS NULL OR "
            "(length(quiet_hours_end) = 5 AND substr(quiet_hours_end, 3, 1) = ':')",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_week_start_day_range", type_="check")
        batch_op.drop_constraint("ck_users_quiet_hours_start_format", type_="check")
        batch_op.drop_constraint("ck_users_quiet_hours_end_format", type_="check")

    with op.batch_alter_table("habits") as batch_op:
        batch_op.drop_constraint("ck_habits_target_hour_range", type_="check")
        batch_op.drop_constraint("ck_habits_target_minute_range", type_="check")

    with op.batch_alter_table("reminder_events") as batch_op:
        batch_op.alter_column(
            "scheduled_local_date",
            existing_type=sa.Date(),
            nullable=False,
            server_default="1970-01-01",
        )
        batch_op.alter_column(
            "dedupe_key",
            existing_type=sa.String(length=190),
            nullable=False,
            server_default="legacy",
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=None,
        )
