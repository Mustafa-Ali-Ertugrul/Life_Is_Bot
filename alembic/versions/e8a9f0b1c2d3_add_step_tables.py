"""add step tables

Revision ID: e8a9f0b1c2d3
Revises: c5d6e7f8b9a0
Create Date: 2026-08-02 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e8a9f0b1c2d3"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f8b9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "step_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("daily_target", sa.Integer(), nullable=False),
        sa.Column("reminder_hour", sa.Integer(), nullable=False),
        sa.Column("reminder_minute", sa.Integer(), nullable=False),
        sa.Column("days_of_week", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "daily_target >= 0 AND daily_target <= 100000",
            name="ck_step_settings_daily_target_range",
        ),
        sa.CheckConstraint(
            "reminder_hour >= 0 AND reminder_hour <= 23",
            name="ck_step_settings_reminder_hour_range",
        ),
        sa.CheckConstraint(
            "reminder_minute >= 0 AND reminder_minute <= 59",
            name="ck_step_settings_reminder_minute_range",
        ),
    )
    op.create_index("ix_step_settings_user_active", "step_settings", ["user_id", "is_active"])

    op.create_table(
        "step_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("steps", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "log_date", name="uq_step_logs_user_date"),
        sa.CheckConstraint(
            "steps >= 0 AND steps <= 200000",
            name="ck_step_logs_steps_range",
        ),
    )
    op.create_index("ix_step_logs_user_date", "step_logs", ["user_id", "log_date"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_step_logs_user_date", table_name="step_logs")
    op.drop_table("step_logs")
    op.drop_index("ix_step_settings_user_active", table_name="step_settings")
    op.drop_table("step_settings")
