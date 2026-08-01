"""add habits table

Revision ID: b5a6c7d8e9f0
Revises: f1e2d3c4b5a6
Create Date: 2026-08-01 16:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b5a6c7d8e9f0"
down_revision: Union[str, Sequence[str], None] = "f1e2d3c4b5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "habits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("target_hour", sa.Integer(), nullable=False),
        sa.Column("target_minute", sa.Integer(), nullable=False),
        sa.Column("days_of_week", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_habits_user_active", "habits", ["user_id", "is_active"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_habits_user_active", table_name="habits")
    op.drop_table("habits")
