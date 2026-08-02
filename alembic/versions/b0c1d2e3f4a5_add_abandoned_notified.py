"""add abandoned_notified to notification_logs

Revision ID: b0c1d2e3f4a5
Revises: a5b6c7d8e9f0
Create Date: 2026-08-03 09:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "a5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("notification_logs") as batch_op:
        batch_op.add_column(
            sa.Column("abandoned_notified", sa.Boolean(), nullable=False, server_default="0")
        )
    op.execute("UPDATE notification_logs SET abandoned_notified = 1 WHERE status = 'abandoned'")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("notification_logs") as batch_op:
        batch_op.drop_column("abandoned_notified")
