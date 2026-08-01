"""add supplement plans table

Revision ID: c5d6e7f8b9a0
Revises: b4c5d6e7f8a9
Create Date: 2026-08-02 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c5d6e7f8b9a0"
down_revision: Union[str, Sequence[str], None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "supplement_plans",
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
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("target_hour BETWEEN 0 AND 23", name="ck_supplement_plans_target_hour_range"),
        sa.CheckConstraint("target_minute BETWEEN 0 AND 59", name="ck_supplement_plans_target_minute_range"),
        sa.CheckConstraint(
            "with_food IN ('empty', 'full', 'any')", name="ck_supplement_plans_with_food"
        ),
        sa.CheckConstraint(
            "start_date IS NULL OR end_date IS NULL OR start_date <= end_date",
            name="ck_supplement_plans_date_range",
        ),
    )
    op.create_index("ix_supplement_plans_user_active", "supplement_plans", ["user_id", "is_active"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_supplement_plans_user_active", table_name="supplement_plans")
    op.drop_table("supplement_plans")
