"""add onboarding answers and user profile fields

Revision ID: a2b3c4d5e6f7
Revises: b0c1d2e3f4a5
Create Date: 2026-08-02 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("profile_type", sa.String(length=20), nullable=True))
    op.add_column(
        "users", sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("onboarding_skipped", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "onboarding_answers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("question_key", sa.String(length=30), nullable=False),
        sa.Column("answer_value", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "question_key", name="uq_onboarding_user_question"),
    )
    op.create_index("ix_onboarding_answers_user", "onboarding_answers", ["user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_onboarding_answers_user", table_name="onboarding_answers")
    op.drop_table("onboarding_answers")
    op.drop_column("users", "onboarding_skipped")
    op.drop_column("users", "onboarding_completed_at")
    op.drop_column("users", "profile_type")
