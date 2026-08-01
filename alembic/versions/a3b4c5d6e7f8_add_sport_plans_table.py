"""add sport plans table

Revision ID: a3b4c5d6e7f8
Revises: f4e5d6c7b8a9
Create Date: 2026-08-02 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "f4e5d6c7b8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "sport_plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sport_type", sa.String(length=64), nullable=False),
        sa.Column("target_hour", sa.Integer(), nullable=False),
        sa.Column("target_minute", sa.Integer(), nullable=False),
        sa.Column("days_of_week", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sport_plans_user_active", "sport_plans", ["user_id", "is_active"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_sport_plans_user_active", table_name="sport_plans")
    op.drop_table("sport_plans")
