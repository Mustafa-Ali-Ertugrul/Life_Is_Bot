"""add medication plans table

Revision ID: a0b1c2d3e4f5
Revises: e8a9f0b1c2d3
Create Date: 2026-08-02 16:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "e8a9f0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "medication_plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("dose", sa.String(length=80), nullable=True),
        sa.Column("with_food", sa.String(length=16), nullable=False),
        sa.Column("target_hour", sa.Integer(), nullable=False),
        sa.Column("target_minute", sa.Integer(), nullable=False),
        sa.Column("days_of_week", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "target_hour BETWEEN 0 AND 23", name="ck_medication_plans_target_hour_range"
        ),
        sa.CheckConstraint(
            "target_minute BETWEEN 0 AND 59", name="ck_medication_plans_target_minute_range"
        ),
        sa.CheckConstraint(
            "with_food IN ('empty', 'full', 'any')", name="ck_medication_plans_with_food"
        ),
        sa.CheckConstraint(
            "start_date IS NULL OR end_date IS NULL OR start_date <= end_date",
            name="ck_medication_plans_date_range",
        ),
    )
    op.create_index("ix_medication_plans_user_active", "medication_plans", ["user_id", "is_active"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_medication_plans_user_active", table_name="medication_plans")
    op.drop_table("medication_plans")
