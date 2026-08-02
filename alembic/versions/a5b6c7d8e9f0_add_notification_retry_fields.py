"""add notification retry fields

Revision ID: a5b6c7d8e9f0
Revises: a0b1c2d3e4f5
Create Date: 2026-08-02 17:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a5b6c7d8e9f0"
down_revision: Union[str, Sequence[str], None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("notification_logs") as batch_op:
        batch_op.add_column(
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True)
        )
    op.execute("UPDATE notification_logs SET retry_count = 99 WHERE status = 'failed'")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("notification_logs") as batch_op:
        batch_op.drop_column("next_retry_at")
        batch_op.drop_column("retry_count")
