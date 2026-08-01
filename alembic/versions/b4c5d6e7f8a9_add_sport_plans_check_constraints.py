"""add sport plans check constraints

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-08-02 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("sport_plans") as batch_op:
        batch_op.create_check_constraint(
            "ck_sport_plans_target_hour_range", "target_hour BETWEEN 0 AND 23"
        )
        batch_op.create_check_constraint(
            "ck_sport_plans_target_minute_range", "target_minute BETWEEN 0 AND 59"
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("sport_plans") as batch_op:
        batch_op.drop_constraint("ck_sport_plans_target_hour_range", type_="check")
        batch_op.drop_constraint("ck_sport_plans_target_minute_range", type_="check")
